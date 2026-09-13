"""Local demo checks: real services, explicitly synthetic transport and facts."""

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from buildbox_router.api import create_app
from buildbox_router.auth import password_hash
from buildbox_router.composition import product_services
from buildbox_router.config import Settings
from buildbox_router.errors import DomainError
from buildbox_router.execution_composition import compose_execution
from buildbox_router.execution_contracts import TransitionRequest
from buildbox_router.planning_storage import PlanningStorage
from buildbox_router.worker import run_once
from fastapi.testclient import TestClient

from .conftest import ctx
from .stakeholder_setup import setup_demo
from .test_unblock import loopback as loopback


def composed(rt, loopback):
    services = product_services(PlanningStorage(rt.store.engine))
    manifest = setup_demo(rt, loopback, services)
    execution = compose_execution(
        rt.store, loopback.registry, services.selector, retention_seconds=60
    )
    execution.gateway.retain_seconds = 60
    auth = Path(rt.store.engine.url.database).parent / "demo-auth.json"
    auth.write_text(
        json.dumps(
            [
                {
                    "username": "fixture",
                    "owner": "alice",
                    "salt": "0" * 32,
                    "password_hash": password_hash("synthetic-test-password", "0" * 32),
                }
            ]
        )
    )
    app = create_app(
        Settings(identity_mode="shared", auth_file=str(auth)), services, execution, rt.store
    )
    app.state.demo_manifest = manifest
    return services, execution, app, manifest


def enable(rt, scenario):
    rt.store.transition(
        "alice",
        scenario.policy,
        TransitionRequest(
            expected_sequence=1,
            status="sandbox_enabled",
            admission_id=scenario.admission_id,
        ),
    )


def test_demo_absent_from_normal_product_and_tenant_scoped(rt, loopback):
    _, _, app, _ = composed(rt, loopback)
    with TestClient(
        app,
        headers={
            "Authorization": "Basic "
            + base64.b64encode(b"fixture:synthetic-test-password").decode()
        },
    ) as client:
        assert client.get("/api/studio/demo").status_code == 200
        app.state.demo_manifest = None
        assert client.get("/api/studio/demo").status_code == 404


def test_three_scenarios_derive_routes_from_real_filter_and_pin(rt, loopback):
    services, _, _, manifest = composed(rt, loopback)
    a, b, c = manifest.scenarios
    assert a.selected == "fixture-small-local"
    assert b.selected == c.selected == "fixture-medium-local"
    assert "reviewer explicitly pinned" in b.explanation
    assert all(
        rt.store.policy("alice", s.policy).transition.status == "draft" for s in manifest.scenarios
    )
    wf = rt.store.policy("alice", c.policy).policy.workflow
    assert services.selector.filter(wf, manifest.catalog).eligible == ("fixture-medium-local",)
    wf_b = rt.store.policy("alice", b.policy).policy.workflow
    assert (
        services.selector.rank(
            wf_b, manifest.catalog, services.selector.filter(wf_b, manifest.catalog)
        )[0]
        == "fixture-small-local"
    )
    assert all(
        f.provenance.kind == "synthetic"
        for f in (e.supported_parameters for e in manifest.catalog.eligibility)
    )


@pytest.mark.parametrize("index", [0, 1, 2])
def test_demo_workflow_uses_actual_worker_and_persisted_attempts(rt, loopback, index):
    services, execution, app, manifest = composed(rt, loopback)
    scenario = manifest.scenarios[index]
    enable(rt, scenario)
    with TestClient(
        app,
        headers={
            "Authorization": "Basic "
            + base64.b64encode(b"fixture:synthetic-test-password").decode()
        },
    ) as client:
        response = client.post(
            "/api/sandbox/runs",
            headers={"Idempotency-Key": "demo-workflow-" + str(index)},
            json={"policy": scenario.policy.model_dump(), "inputs": scenario.inputs},
        )
        assert response.status_code == 202, response.text
        identifier = response.json()["id"]
        assert run_once(services, execution=execution)
        assert client.get("/api/sandbox/runs/" + identifier).json()["status"] == "succeeded"
        assert len(rt.store.outputs_for_run("alice", identifier)) == 1
        assert len(rt.store.attempts("alice", identifier)) == 1


def test_demo_fallback_stream_persists_without_hiding_failed_attempt(rt, loopback):
    _, execution, app, manifest = composed(rt, loopback)
    scenario = manifest.fallback
    enable(rt, scenario)
    _, secret = execution.keys.issue(
        ctx(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        scopes=("chat:complete", "models:read", "runs:read"),
        aliases=(scenario.alias,),
        max_cost_micro_usd=1000,
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={
                "Authorization": "Bearer " + secret,
                "Idempotency-Key": "demo-fallback-stream",
            },
            json={
                "model": scenario.alias,
                "messages": [{"role": "user", "content": "DEMO_FAIL_ONCE unique-demo-test"}],
                "max_tokens": 128,
                "stream": True,
            },
        )
        assert response.status_code == 200 and "[DONE]" in response.text, response.text
        identifier = response.headers["X-Request-ID"]
        attempts = sorted(rt.store.attempts("alice", identifier), key=lambda a: a.attempt)
        assert len(attempts) == 2
        assert attempts[0].usage.actual_micro_usd is None
        assert attempts[1].status == "succeeded"
        assert (
            rt.store.output("alice", identifier).value["choices"][0]["message"]["content"]
            == manifest.scenarios[0].expected
        )
        with pytest.raises(DomainError):
            rt.store.output("bob", identifier)
