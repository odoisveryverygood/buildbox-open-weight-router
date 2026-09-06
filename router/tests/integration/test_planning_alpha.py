import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from buildbox_router.api import create_app
from buildbox_router.auth import password_hash
from buildbox_router.composition import fixture_services
from buildbox_router.config import Settings
from buildbox_router.errors import DomainError
from buildbox_router.planning import planning_examples
from buildbox_router.planning_contracts import PlanInput
from buildbox_router.planning_storage import PlanningStorage
from buildbox_router.runtime import OpenRouterRole, RoleApproval, approval_for, guarded_request
from buildbox_router.worker import run_once
from fastapi.testclient import TestClient
from sqlalchemy import text


def submit(client, index=0, key="test-request-0001", **changes):
    data = {"intake": planning_examples()[index].intake.model_dump(mode="json"), **changes}
    response = client.post("/api/plans", json=data, headers={"Idempotency-Key": key})
    assert response.status_code == 201, response.text
    return response.json()


def path(view):
    return f"/api/plans/{view['plan']['id']}/versions/{view['plan']['version']}"


@pytest.mark.parametrize(
    "index,kinds",
    [
        (0, ["code", "llm", "human_approval"]),
        (1, ["llm", "tool", "llm", "human_approval"]),
        (2, ["bounded_agent", "human_approval"]),
    ],
)
def test_three_examples_are_real_lane_compositions(storage, index, kinds):
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        view = submit(client, index)
        assert view["job"]["status"] == "queued"
        assert run_once(services)
        saved = client.get(path(view)).json()
        assert saved["job"]["status"] == "succeeded", saved
        result = saved["result"]
        assert result["status"] == ("blocked" if index == 2 else "provisional"), result
        assert [n["kind"] for n in result["workflow"]["nodes"]] == kinds
        assert result["catalog"]["synthetic"]
        if index == 2:
            assert result["recommendation"] is None
            assert any(
                "tool-call" in reason
                for reasons in result["exclusions"].values()
                for reason in reasons
            )
            assert client.post(path(view) + "/policy", json={}).status_code == 400
            return
        assert result["recommendation"]["workflow_version"] == 1
        assert result["evaluation_status"] == "not_run"
        exported = client.post(path(view) + "/policy", json={})
        assert exported.status_code == 200, exported.text
        policy = exported.json()
        assert (
            not policy["active"]
            and not policy["production_write"]
            and not policy["execution_tools"]
        )
        assert policy["requires_human_approval"]


def test_revision_idempotency_staleness_and_saved_answers(storage):
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        first = submit(client)
        assert submit(client)["job"]["id"] == first["job"]["id"]
        run_once(services)
        data = first["plan"]["input"]
        data["intake"]["constraints"]["max_cost_per_1k_tokens"] = 0
        data["answers"] = [{"question_id": "user-note", "answer": "Corrected budget to zero"}]
        response = client.post(
            path(first) + "/revise", json=data, headers={"Idempotency-Key": "revision-key-0001"}
        )
        assert response.status_code == 201, response.text
        second = response.json()
        assert second["plan"]["version"] == 2
        assert client.get(path(first)).json()["stale"]
        assert client.post(path(first) + "/policy", json={}).status_code == 409
        assert (
            client.post(
                path(first) + "/revise", json=data, headers={"Idempotency-Key": "revision-key-0002"}
            ).status_code
            == 409
        )
        run_once(services)
        loaded = client.get(path(second)).json()
        assert loaded["result"]["workflow"]["version"] == 2
        assert loaded["result"]["recommendation"]["workflow_version"] == 2
        assert loaded["plan"]["input"]["answers"][0]["answer"] == "Corrected budget to zero"


@pytest.mark.parametrize(
    "requirements,word",
    [
        ({"input_modality": "image"}, "Image"),
        ({"deployment": "self_hosted"}, "Self-hosted"),
        ({"structured_output": True}, "structured"),
        ({"tool_calling": True}, "tool-call"),
    ],
)
def test_unverified_hard_requirements_never_get_synthetic_success(storage, requirements, word):
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        view = submit(client, requirements=requirements)
        run_once(services)
        result = client.get(path(view)).json()["result"]
        assert result["status"] == "blocked" and result["recommendation"] is None
        assert word in " ".join(result["missing_facts"])
        assert client.post(path(view) + "/policy", json={}).status_code == 400


def test_unknown_public_snapshot_and_unapproved_public_call(storage, monkeypatch):
    services = fixture_services(storage)
    monkeypatch.setattr(
        "buildbox_router.planning.public_sources", lambda _: pytest.fail("No egress authorized")
    )
    with TestClient(create_app(services=services)) as client:
        view = submit(client, catalog_mode="public_snapshot")
        run_once(services)
        result = client.get(path(view)).json()["result"]
        assert result["status"] == "blocked" and not result["catalog"]["synthetic"]
        second = submit(client, key="request-runtime-01", catalog_mode="runtime_public")
        run_once(services)
        assert client.get(path(second)).json()["job"]["status"] == "failed"


def test_deterministic_no_model_no_research(storage, monkeypatch):
    monkeypatch.setattr(
        "buildbox_router.planning.public_sources",
        lambda _: pytest.fail("No model means no research"),
    )
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        data = planning_examples()[0].intake.model_dump(mode="json")
        data["description"] = "lowercase text"
        view = submit(client, intake=data, catalog_mode="runtime_public")
        run_once(services)
        result = client.get(path(view)).json()["result"]
        assert result["status"] == "deterministic" and result["recommendation"]["assignments"] == []


def test_questions_and_failing_provider_have_no_sample_fallback(storage, monkeypatch):
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        data = planning_examples()[0].intake.model_dump(mode="json")
        data["description"] = "Automate my business"
        view = submit(client, intake=data)
        run_once(services)
        assert client.get(path(view)).json()["result"]["interpretation"]["questions"]

        def unavailable(_):
            raise TimeoutError("Bearer do-not-echo-secret")

        monkeypatch.setattr("buildbox_router.planning.public_sources", unavailable)
        view = submit(
            client,
            key="failure-request-1",
            catalog_mode="runtime_public",
            processing={"public_research": True},
        )
        run_once(services)
        response = client.get(path(view))
        assert response.json()["job"]["status"] == "failed"
        assert response.json()["result"] is None and "do-not-echo" not in response.text


def test_cancellation_blocks_completion_and_recovery(storage):
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        view = submit(client)
        assert client.post(path(view) + "/cancel", json={}).json()["job"]["status"] == "cancelled"
        assert not run_once(services)
        assert client.get(path(view)).json()["result"] is None


@pytest.mark.parametrize("state", ["reserved", "known", "uncertain"])
def test_paid_work_is_not_repeated_after_lease_expiry(storage, state):
    store = PlanningStorage(storage.engine)
    view = store.submit("owner", "reserve-request", PlanInput(intake=planning_examples()[0].intake))
    owner, job = store.claim()
    call_id = store.reserve_call(owner, job, "interpretation", "approval1", 1000, 2000)
    if state != "reserved":
        store.settle_call(call_id, 1000 if state == "known" else None, {})
    with storage.engine.begin() as conn:
        conn.execute(
            text("UPDATE jobs SET updated_at=:old WHERE id=:id"),
            {"old": time.time() - 120, "id": job.id},
        )
    assert store.claim() is None
    assert store.job(owner, view.job.id).status == "uncertain"


def test_atomic_budget_across_jobs(storage):
    store = PlanningStorage(storage.engine)
    for i in range(2):
        store.submit(
            "owner", f"budget-request-{i}", PlanInput(intake=planning_examples()[0].intake)
        )
    claims = [store.claim(), store.claim()]

    def reserve(claim):
        owner, job = claim
        try:
            return store.reserve_call(owner, job, "interpretation", "shared-approval", 1000, 1000)
        except DomainError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, claims))
    assert sum(x is not None for x in results) == 1


def test_shared_auth_ownership_on_all_new_endpoints(storage, tmp_path):
    users = [
        {
            "username": name,
            "owner": name,
            "salt": "a" * 32,
            "password_hash": password_hash("synthetic-test-password", "a" * 32),
        }
        for name in ("alice", "bob")
    ]
    auth = tmp_path / "users.json"
    auth.write_text(json.dumps(users))
    settings = Settings(identity_mode="shared", auth_file=str(auth))
    with TestClient(create_app(settings, fixture_services(storage))) as client:
        assert client.get("/api/planning-capabilities").status_code == 401
        client.auth = ("alice", "synthetic-test-password")
        view = submit(client)
        assert client.get("/api/examples").status_code == 404
        client.auth = ("bob", "synthetic-test-password")
        assert client.get(path(view)).status_code == 404
        for action in ("cancel", "policy"):
            assert client.post(path(view) + "/" + action, json={}).status_code == 404
        assert (
            client.post(
                path(view) + "/revise",
                json=view["plan"]["input"],
                headers={"Idempotency-Key": "other-tenant-key"},
            ).status_code
            == 404
        )


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "https://huggingface.co.evil/api/models/Qwen/Qwen3-8B",
        "https://huggingface.co/api/models/Qwen/Qwen3-8B?token=x",
        "https://openrouter.ai/api/v1/chat/completions",
        "https://user:pass@huggingface.co/api/models/Qwen/Qwen3-8B",
    ],
)
def test_runtime_transport_denies_unapproved_destinations(url):
    with pytest.raises(DomainError):
        guarded_request(url)


def test_runtime_mixed_private_dns_is_denied(monkeypatch):
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443)), (2, 1, 6, "", ("8.8.8.8", 443))],
    )
    with pytest.raises(DomainError, match="DNS"):
        guarded_request("https://huggingface.co/api/models/Qwen/Qwen3-8B")


def test_no_permission_is_not_key_discovery():
    with pytest.raises(DomainError, match="permission"):
        approval_for(None, "owner", "interpretation")


def role_approval():
    return RoleApproval(
        id="test-only-approval",
        owner="owner",
        role="interpretation",
        provider="openrouter",
        approved=True,
        permission_reference="Offline test only; not a live permission",
        expires_at=datetime.now(UTC) + timedelta(days=1),
        key_environment="ROUTER_TEST_KEY",
        model="vendor/model",
        endpoint="provider/explicit-variant",
        cap_usd=0.1,
        max_prompt_per_million=1.0,
        max_completion_per_million=2.0,
    )


def test_openrouter_exact_endpoint_required_params_budget_and_metadata(storage, monkeypatch):
    store = PlanningStorage(storage.engine)
    store.submit("owner", "adapter-test", PlanInput(intake=planning_examples()[0].intake))
    owner, job = store.claim()
    calls = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/endpoints"):
            return {
                "data": {
                    "endpoints": [
                        {
                            "tag": "provider/explicit-variant",
                            "supported_parameters": ["max_tokens", "response_format"],
                            "pricing": {
                                "prompt": "0.000001",
                                "completion": "0.000002",
                                "request": "0",
                            },
                        }
                    ]
                }
            }
        return {
            "id": "generation-123",
            "model": "vendor/model",
            "provider": "Provider",
            "usage": {"cost": 0.001, "total_tokens": 100},
            "choices": [{"message": {"content": "{}"}}],
        }

    monkeypatch.setattr("buildbox_router.runtime.guarded_request", request)
    monkeypatch.setenv("ROUTER_TEST_KEY", "synthetic-not-a-real-key")
    adapter = OpenRouterRole(role_approval(), store, owner, job, 0.1, lambda: None)
    assert adapter.complete(role="interpretation", prompt="Synthetic input") == "{}"
    provider = calls[-1][1]["payload"]["provider"]
    assert (
        provider["only"] == ["provider/explicit-variant"] and provider["allow_fallbacks"] is False
    )
    assert (
        provider["require_parameters"] and provider["zdr"] and provider["data_collection"] == "deny"
    )
    assert store.job(owner, job.id).accounted_usd == 0.001
    with store.engine.connect() as conn:
        metadata = conn.execute(text("SELECT metadata FROM provider_calls")).scalar_one()
    assert "generation-123" in metadata and "synthetic-not-a-real-key" not in metadata


def test_paid_budget_exhaustion_happens_before_paid_request(storage, monkeypatch):
    store = PlanningStorage(storage.engine)
    store.submit("owner", "budget-zero-test", PlanInput(intake=planning_examples()[0].intake))
    owner, job = store.claim()
    monkeypatch.setenv("ROUTER_TEST_KEY", "synthetic-not-a-real-key")

    def request(url, **kwargs):
        assert url.endswith("/endpoints")
        return {
            "data": {
                "endpoints": [
                    {
                        "tag": "provider/explicit-variant",
                        "supported_parameters": ["max_tokens", "response_format"],
                        "pricing": {"prompt": "0.000001", "completion": "0.000002", "request": "0"},
                    }
                ]
            }
        }

    monkeypatch.setattr("buildbox_router.runtime.guarded_request", request)
    with pytest.raises(DomainError, match="budget exhausted"):
        OpenRouterRole(role_approval(), store, owner, job, 0, lambda: None).complete(
            role="interpretation", prompt="test"
        )


def test_local_model_output_is_validated_and_usage_retained_on_failure(monkeypatch):
    from buildbox_router.local_inference import interpret_local
    from pydantic import ValidationError

    captured = []

    def request(path, value, check):
        check()
        if path == "/api/tags":
            return {"models": [{"name": "test:local", "size": 100, "digest": "abc123"}]}
        assert value["stream"] is False and value["options"]["num_predict"] == 1400
        assert value["format"]["$defs"]["Node"]["properties"]["outputs"]["minItems"] == 1
        return {
            "model": "test:local",
            "done": True,
            "done_reason": "stop",
            "eval_count": 12,
            "message": {
                "content": '{"title":"bad graph","nodes":[{"id":"a","kind":"llm","purpose":"classify","outputs":[]}]}'
            },
        }

    monkeypatch.setattr("buildbox_router.local_inference.local_request", request)
    with pytest.raises(ValidationError):
        interpret_local(
            "test:local",
            planning_examples()[0].intake,
            "test-id",
            "[]",
            lambda: None,
            captured.append,
        )
    assert captured[0]["eval_count"] == 12


def test_local_model_has_no_cloud_or_download_fallback(monkeypatch):
    from buildbox_router.local_inference import interpret_local

    calls = []

    def request(path, value, check):
        calls.append(path)
        return {"models": []}

    monkeypatch.setattr("buildbox_router.local_inference.local_request", request)
    with pytest.raises(DomainError):
        interpret_local("test:cloud", planning_examples()[0].intake, "id", "[]", lambda: None)
    assert not calls
    with pytest.raises(DomainError):
        interpret_local("test:local", planning_examples()[0].intake, "id", "[]", lambda: None)
    assert calls == ["/api/tags"]


def test_selecting_runtime_never_replays_even_an_exact_example(storage):
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        view = submit(client, processing={"inference": "local_model"})
        run_once(services)
        result = client.get(path(view)).json()
        assert result["job"]["status"] == "failed" and result["result"] is None


def test_legacy_routes_cannot_bypass_versioned_plan_policy(storage):
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        view = submit(client)
        run_once(services)
        job = view["job"]["id"]
        for resource in (
            f"/api/jobs/{job}",
            f"/api/recommendations/{job}",
            f"/api/recommendations/{job}/evidence",
        ):
            assert client.get(resource).status_code == 400
        assert client.post(f"/api/recommendations/{job}/policy", json={}).status_code == 400


def test_candidate_budget_across_distinct_roles(storage):
    store = PlanningStorage(storage.engine)
    store.submit("owner", "candidate-budget", PlanInput(intake=planning_examples()[0].intake))
    owner, job = store.claim()
    store.reserve_call(owner, job, "interpretation", "approval-one", 1000, 2000, 1000)
    with pytest.raises(DomainError, match="Candidate planning budget"):
        store.reserve_call(owner, job, "research", "approval-two", 1000, 2000, 1000)


def test_text_code_does_not_bypass_image_requirement(storage):
    services = fixture_services(storage)
    data = planning_examples()[0].intake.model_dump(mode="json")
    data["description"] = "lowercase text"
    with TestClient(create_app(services=services)) as client:
        view = submit(client, intake=data, requirements={"input_modality": "image"})
        run_once(services)
        assert client.get(path(view)).json()["result"]["status"] == "blocked"


def test_unauthenticated_fixture_rejects_remote_clients(storage):
    with TestClient(
        create_app(services=fixture_services(storage)), client=("192.0.2.1", 1234)
    ) as client:
        assert client.get("/api/planning-examples").status_code == 403
