import asyncio
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from buildbox_router.api import create_app
from buildbox_router.composition import fixture_services
from buildbox_router.errors import DomainError
from buildbox_router.evidence_contracts import EndpointRecord, PriceComponent
from buildbox_router.execution_contracts import (
    ProviderCredentialReference,
    TargetConfiguration,
    WorkflowRunRequest,
)
from buildbox_router.execution_ports import ExecutionServices
from buildbox_router.gateway.adapters import TargetAdapters
from buildbox_router.gateway.preflight import cost_bound
from fastapi.testclient import TestClient

from .conftest import ctx


def endpoint(rt):
    fact = rt.fact
    return EndpointRecord(
        id="endpoint-synthetic",
        artifact_id=rt.target.configuration.artifact_id,
        routing_model_id="synthetic/test",
        endpoint_tag="synthetic-provider/region",
        provider=fact("synthetic-provider"),
        metadata_url="https://openrouter.ai/api/v1/models/synthetic/test/endpoints",
        serving_url=fact("https://untrusted.example/never-follow"),
        served_revision=fact("test"),
        supported_parameters=fact(("max_tokens", "temperature")),
        context_tokens=fact(4096),
        max_prompt_tokens=fact(2048),
        max_completion_tokens=fact(128),
        quantization=fact("fp16"),
        hardware=fact("test"),
        region=fact("local"),
        privacy=fact("zdr"),
        provider_restrictions=fact("none"),
        conditional_pricing=fact("none"),
        prices=(
            PriceComponent(
                component="prompt", raw_amount="0", unit="token", usd_per_million_tokens="0"
            ),
            PriceComponent(
                component="completion", raw_amount="0", unit="token", usd_per_million_tokens="0"
            ),
            PriceComponent(component="request", raw_amount="0", unit="request"),
        ),
        evidence_ids=("fixture-facts",),
        limitations=("Synthetic software fixture, not pricing evidence",),
    )


def hosted(rt):
    rt.target = TargetConfiguration(
        configuration=rt.target.configuration,
        catalog_id=rt.target.catalog_id,
        endpoint=endpoint(rt),
        limitations=("Synthetic",),
    )
    rt.credential = ProviderCredentialReference(
        id="credential",
        tenant_id="alice",
        adapter_id="openrouter",
        secret_reference="synthetic-secret-reference",
        approval_reference="fixture-approval",
        expires_at=rt.credential.expires_at,
    )


def test_openrouter_pinned_controls_no_arbitrary_url_or_auto(rt, monkeypatch):
    from buildbox_router.gateway import adapters

    hosted(rt)
    seen = []

    def request(url, *, payload, key, check):
        check()
        seen.append((url, payload))  # Never retain keys even in test diagnostics.
        assert key == "recorded-not-a-credential"
        return {
            "model": "synthetic/test",
            "provider": "synthetic-provider",
            "created": 0,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "synthetic"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3, "cost": 0},
        }

    monkeypatch.setattr(adapters, "guarded_request", request)
    rt.gateway.inference = TargetAdapters(lambda t, ref: "recorded-not-a-credential")
    context = ctx(key=rt.key)
    result = asyncio.run(rt.gateway.complete(context, rt.request))
    assert result.choices[0].message.content == "synthetic"
    url, payload = seen[0]
    assert url == "https://openrouter.ai/api/v1/chat/completions"
    assert payload["model"] == "synthetic/test"
    assert payload["provider"] == {
        "only": ["synthetic-provider/region"],
        "order": ["synthetic-provider/region"],
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": "deny",
        "zdr": True,
        "max_price": {"prompt": 0.0, "completion": 0.0},
    }
    assert rt.store.trace("alice", context.request_id).served_endpoint.value == "synthetic-provider"


@pytest.mark.parametrize(
    "change", ["missing", "conditional", "extra", "unknown_unit", "request_surcharge"]
)
def test_missing_or_unbounded_prices_block(rt, change):
    hosted(rt)
    e = rt.target.endpoint
    if change == "missing":
        e = e.model_copy(update={"prices": e.prices[:-1]})
    elif change == "conditional":
        e = e.model_copy(update={"conditional_pricing": rt.fact("tiered")})
    elif change == "extra":
        e = e.model_copy(
            update={
                "prices": e.prices
                + (PriceComponent(component="image", raw_amount="0.10", unit="image"),)
            }
        )
    elif change == "unknown_unit":
        e = e.model_copy(
            update={
                "prices": e.prices
                + (
                    PriceComponent(
                        component="unrecognized", raw_amount="0", unit="unknown", currency="unknown"
                    ),
                )
            }
        )
    else:
        e = e.model_copy(
            update={
                "prices": e.prices[:-1]
                + (PriceComponent(component="request", raw_amount="0.01", unit="request"),)
            }
        )
    with pytest.raises(DomainError):
        cost_bound(rt.target.model_copy(update={"endpoint": e}), 100, 20)


def test_sdk_shaped_http_auth_and_live_sse_injected_port(rt, monkeypatch):
    from buildbox_router import execution_api

    # Explicit test-only admission plumbing, keeping SYNTHETIC facts. Normal
    # HTTP composition still refuses them; no operational grants fabricated.
    monkeypatch.setattr(execution_api, "repository", lambda request: rt.store)
    monkeypatch.setattr(
        execution_api,
        "enabled",
        lambda request, tenant, ref: rt.authority.policy(ctx(tenant), ref)[0],
    )
    app = create_app(
        services=fixture_services(rt.store),
        execution_services=ExecutionServices(rt.gateway, rt.runner, rt.keys, SimpleNamespace()),
    )
    headers = {"Authorization": "Bearer " + rt.raw}
    with TestClient(app) as client:
        assert client.get("/v1/models").status_code == 401
        assert client.get("/v1/models", headers=headers).json()["data"][0]["id"] == "test-alias"
        body = rt.request.model_dump()
        response = client.post("/v1/chat/completions", headers=headers, json=body)
        assert response.status_code == 200
        assert response.json()["object"] == "chat.completion"
        assert response.headers["X-Buildbox-Quality"] == "untested_provisional"
        assert (
            client.post(
                "/v1/chat/completions", headers=headers, json=body | {"tools": []}
            ).status_code
            == 400
        )
        assert len(rt.inference.calls) == 1
        rt.inference.frames = [
            {"choices": [{"index": 0, "delta": {"content": "incremental"}, "finish_reason": None}]},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        ]
        streamed = client.post(
            "/v1/chat/completions", headers=headers, json=body | {"stream": True}
        )
        assert streamed.headers["content-type"].startswith("text/event-stream")
        assert '"content":"incremental"' in streamed.text
        assert streamed.text.endswith("data: [DONE]\n\n")


def test_new_process_persisted_attempt_and_request(rt):
    context = ctx(key=rt.key)
    asyncio.run(rt.gateway.complete(context, rt.request))
    program = """
import sys
from sqlalchemy import create_engine
from buildbox_router.execution_storage import SandboxStorage
from buildbox_router.execution_contracts import RunAttempt
s = SandboxStorage(create_engine(sys.argv[1]))
assert s.request_state('alice', sys.argv[2]) == 'succeeded'
a = RunAttempt.model_validate_json(s.latest('alice', 'attempt', sys.argv[2])[1])
assert a.usage.actual_micro_usd == 0
print('fresh-process reload passed')
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(rt.store.engine.url), context.request_id],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "fresh-process reload passed"


def test_revoked_after_dispatch_no_next_workflow_stage(rt):
    rt.inference.after_call = lambda: rt.store.revoke_key("alice", rt.key.id, datetime.now(UTC))
    result = asyncio.run(
        rt.runner.submit(
            ctx(key=rt.key), WorkflowRunRequest(policy=rt.ref, inputs={"document": "fixture"})
        )
    )
    assert result.status == "uncertain" and len(rt.inference.calls) == 1


def test_replay_while_running_never_restarts(rt):
    context = ctx()
    value = WorkflowRunRequest(policy=rt.ref, inputs={"document": "fixture"})

    async def execute():
        original = rt.inference.complete

        async def nested(child, call):
            replay = await rt.runner.submit(replace(context, request_id="new-request"), value)
            assert replay.status == "running"
            return await original(child, call)

        rt.inference.complete = nested
        return await rt.runner.submit(context, value)

    assert asyncio.run(execute()).status == "awaiting_approval"
    assert len(rt.inference.calls) == 1


def test_no_model_parallel_dag_and_real_bound_outputs(rt):
    from buildbox_router.execution_contracts import (
        ExecutablePolicy,
        SandboxAdmission,
        TransitionRequest,
        VersionRef,
        digest,
    )
    from buildbox_router.execution_storage import append

    data = rt.policy.model_dump(mode="json")
    data["id"] = "code-policy"
    data["prompts"] = []
    operations = ["text.trim.v1", "text.lowercase.v1", "text.uppercase.v1"]
    for node, stage, operation in zip(
        data["workflow"]["nodes"], data["stages"], operations, strict=True
    ):
        node["kind"] = "code"
        stage.update(prompt=None, configuration_id=None, operation=operation)
        stage["budget"]["max_model_calls"] = 0
    data["workflow"]["nodes"][1]["depends_on"] = []
    data["workflow"]["nodes"][1]["inputs"] = data["workflow"]["nodes"][0]["inputs"]
    data["workflow"]["nodes"][2]["depends_on"] = ["normalize", "classify"]
    policy = ExecutablePolicy.model_validate(data)
    ref = VersionRef(id=policy.id, version=1)
    rt.store._append_policy("alice", policy)
    admission = SandboxAdmission.model_validate(
        rt.admission.model_dump()
        | {
            "id": "code-admission",
            "policy": ref,
            "policy_digest": digest(policy),
            "configuration_ids": (),
        }
    )
    with rt.store.engine.begin() as connection:
        append(connection, "alice", "admission", admission.id, 1, admission)
    rt.store.transition(
        "alice",
        ref,
        TransitionRequest(expected_sequence=1, status="sandbox_enabled", admission_id=admission.id),
    )
    result = asyncio.run(
        rt.runner.submit(ctx(), WorkflowRunRequest(policy=ref, inputs={"document": "MiXeD"}))
    )
    assert result.status == "succeeded" and result.attempt_ids == ()
    assert not rt.inference.calls
    assert rt.store.output("alice", result.output_reference).value == {"result": "MIXED"}


def test_durable_cancel_during_model_stops_next_stage(rt):
    context = ctx()

    async def cancel_then_complete(child, call):
        await rt.runner.cancel(ctx(), context.request_id)
        raise TimeoutError("Model may still bill")

    rt.inference.complete = cancel_then_complete
    result = asyncio.run(
        rt.runner.submit(context, WorkflowRunRequest(policy=rt.ref, inputs={"document": "fixture"}))
    )
    assert result.status == "cancelled"
    assert asyncio.run(rt.runner.get(ctx(), result.id)).status == "cancelled"
