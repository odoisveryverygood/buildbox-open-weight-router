"""Local sandbox completion: real engine, explicitly synthetic exact-port upstream."""

import asyncio

import pytest
from buildbox_router.composition import product_services
from buildbox_router.contracts import WorkloadProfile
from buildbox_router.errors import DomainError
from buildbox_router.execution_composition import compose_execution
from buildbox_router.execution_contracts import (
    ExecutablePolicy,
    TransitionRequest,
    ValidationRule,
    VersionRef,
    WorkflowRunRequest,
    digest,
)
from buildbox_router.execution_storage import append
from buildbox_router.gateway.outcomes import history
from buildbox_router.intelligence.planner import compile_policy, plan
from buildbox_router.planning_storage import PlanningStorage
from buildbox_router.routing_contracts import (
    ExecutionPlan,
    PlanStage,
    PreviewRequest,
    RouterPolicy,
    WhatIfRequest,
)
from buildbox_router.routing_service import draft, preview, what_if
from buildbox_router.worker import run_once
from pydantic import ValidationError

from .advanced_setup import setup_advanced
from .conftest import ctx
from .stakeholder_setup import setup_demo
from .test_unblock import loopback as loopback
from .test_unblock import wire


@pytest.fixture
def sandbox(rt, loopback):
    services = product_services(PlanningStorage(rt.store.engine))
    manifest = setup_demo(rt, loopback, services)
    catalogs, scenarios = setup_advanced(rt, loopback, services, manifest)
    execution = compose_execution(
        rt.store, loopback.registry, services.selector, retention_seconds=60
    )
    return services, execution, catalogs[0], next(s for s in scenarios if s.id == "K")


def activate(rt, ref, admission):
    rt.store.transition(
        "alice",
        ref,
        TransitionRequest(expected_sequence=1, status="sandbox_enabled", admission_id=admission),
    )


def run(rt, sandbox, ref, text="ADVANCED_K"):
    services, execution, _, _ = sandbox
    queued = asyncio.run(
        execution.workflows.submit(ctx(), WorkflowRunRequest(policy=ref, inputs={"input": text}))
    )
    assert run_once(services, execution=execution)
    return asyncio.run(execution.workflows.get(ctx(), queued.id))


def publish(rt, sandbox, request):
    _, _, catalog, _ = sandbox
    decision = preview(rt.store, "alice", request, catalog)
    policy = draft(rt.store, "alice", decision)
    ref = VersionRef(id=policy.id, version=policy.version)
    admission = rt.admission.model_copy(
        update={
            "id": "admit-" + decision.id,
            "policy": ref,
            "policy_digest": digest(policy),
            "configuration_ids": tuple(
                dict.fromkeys(
                    c
                    for s in policy.stages
                    for c in (s.configuration_id, *s.fallback_configuration_ids)
                    if c
                )
            ),
        }
    )
    with rt.store.engine.begin() as conn:
        append(conn, "alice", "admission", admission.id, 1, admission)
    activate(rt, ref, admission.id)
    return decision, policy, ref


def test_k_repair_preserves_output_accounts_both_and_records_outcome(rt, sandbox):
    scenario = sandbox[3]
    activate(rt, scenario.policy, scenario.admission_id)
    result = run(rt, sandbox, scenario.policy)
    assert result.status == "succeeded"
    attempts = sorted(rt.store.attempts("alice", result.id), key=lambda a: a.attempt)
    assert len(attempts) == 2
    original, repair = attempts
    assert original.status == "failed" and original.validation[0].passed is False
    assert repair.status == "succeeded" and repair.validation[0].passed is True
    assert repair.recovery_action == "repair" and repair.fallback_reason == "quality_validation"
    assert original.trace.configuration_id == repair.trace.configuration_id
    assert "Incomplete" in rt.store.output("alice", original.output_reference).value["result"]
    assert original.usage.state == repair.usage.state == "reconciled"
    usage_events = [e for e in rt.store.events("alice", result.id, 0) if e.type == "run.usage"]
    assert len(usage_events) == 2
    outcome = next(o for o in history(rt.store, "alice") if o.run_id == result.id)
    assert outcome.repair_count == 1 and outcome.fallback_count == 0
    assert outcome.failed_validations == 1 and outcome.validation_passed is True
    assert outcome.attempt_count == 2 and outcome.unknown_cost_attempts == 0
    assert outcome.synthetic and not outcome.affects_ranking
    assert not history(rt.store, "bob")
    with pytest.raises(DomainError):
        rt.store.output("bob", original.output_reference)
    # Duplicate submission/read cannot launch another repair or replace the outcome.
    assert len(rt.store.attempts("alice", result.id)) == 2


@pytest.mark.parametrize("repairs", [0, 1, 2])
def test_validation_exhaustion_is_bounded_and_charges_known(rt, sandbox, loopback, repairs):
    catalog = sandbox[2]
    request = PreviewRequest(
        description="Validate bounded output",
        catalog_id=catalog.id,
        overrides=WorkloadProfile(
            input_tokens=4096, output_tokens=128, max_attempts=3, strategy="single"
        ),
        required_terms=("VALID",),
        max_repairs=repairs,
    )
    _, policy, ref = publish(rt, sandbox, request)
    loopback.respond = lambda body: setattr(loopback, "result", wire(content="Incomplete"))
    result = run(rt, sandbox, ref)
    attempts = rt.store.attempts("alice", result.id)
    assert result.status == "failed"
    assert len(attempts) == repairs + 1 == policy.budget.max_model_calls
    assert all(a.usage.actual_micro_usd is not None for a in attempts)
    outcome = next(o for o in history(rt.store, "alice") if o.run_id == result.id)
    assert outcome.repair_count == repairs and outcome.validation_passed is False


def test_validation_pass_skips_repair(rt, sandbox, loopback):
    scenario = sandbox[3]
    activate(rt, scenario.policy, scenario.admission_id)
    loopback.respond = lambda body: setattr(loopback, "result", wire(content="VALID immediately"))
    result = run(rt, sandbox, scenario.policy)
    assert result.status == "succeeded" and len(rt.store.attempts("alice", result.id)) == 1


def test_general_graph_parallel_fanin_order_and_snapshot(rt, sandbox, monkeypatch):
    catalog = sandbox[2]
    graph = ExecutionPlan(
        stages=(
            PlanStage(id="finish", task="summarization", depends_on=("left", "right")),
            PlanStage(id="left", task="coding", depends_on=("start",)),
            PlanStage(id="right", task="debugging", depends_on=("start",)),
            PlanStage(id="start", task="extraction"),
        )
    )
    request = PreviewRequest(
        description="Review and synthesize",
        catalog_id=catalog.id,
        overrides=WorkloadProfile(input_tokens=4096, output_tokens=128),
        execution_plan=graph,
    )
    decision, policy, ref = publish(rt, sandbox, request)
    assert decision.parallel_waves == (("start",), ("left", "right"), ("finish",))
    assert policy.workflow.nodes[-1].inputs["left"].source == "left"
    entered, finished = [], []
    runner = sandbox[1].workflows.runner
    original = runner._stage

    async def observe(context, policy, node, inputs, outputs, data_class):
        entered.append(node)
        if node in ("left", "right"):
            for _ in range(100):
                if "left" in entered and "right" in entered:
                    break
                await asyncio.sleep(0)
            assert "left" in entered and "right" in entered
        if node == "finish":
            assert set(finished) == {"start", "left", "right"}
            assert set(outputs) == {"start", "left", "right"}
        result = await original(context, policy, node, inputs, outputs, data_class)
        finished.append(node)
        return result

    monkeypatch.setattr(runner, "_stage", observe)
    result = run(rt, sandbox, ref, "ADVANCED_G")
    assert result.status == "succeeded" and len(rt.store.attempts("alice", result.id)) == 4
    changed, _ = what_if(
        rt.store,
        "alice",
        decision,
        WhatIfRequest(policy=RouterPolicy(id="custom-cost", weights={"cost": 1})),
    )
    assert changed.execution_plan == decision.execution_plan
    assert rt.store.policy("alice", ref).policy == policy


@pytest.mark.parametrize(
    "stages",
    [
        [{"id": "input", "task": "coding"}],
        [{"id": "a", "task": "coding", "depends_on": ["b"]}],
        [{"id": "a", "task": "coding", "depends_on": ["a"]}],
        [{"id": "a", "task": "coding"}, {"id": "a", "task": "coding"}],
        [{"id": str(i), "task": "coding"} for i in range(9)],
    ],
)
def test_invalid_dags_rejected(stages):
    with pytest.raises(ValidationError):
        ExecutionPlan.model_validate({"stages": stages})


def test_custom_conditional_escalation_and_hard_caps(rt, sandbox):
    catalog = sandbox[2]
    graph = ExecutionPlan(
        stages=(
            PlanStage(
                id="custom",
                task="coding",
                escalate=True,
                validators=(ValidationRule(kind="required_terms", values=("VALID",)),),
            ),
        )
    )
    request = PreviewRequest(
        description="Solve code",
        catalog_id=catalog.id,
        overrides=WorkloadProfile(input_tokens=4096, output_tokens=128),
        execution_plan=graph,
    )
    decision, _, ref = publish(rt, sandbox, request)
    assert decision.stages[0].fallbacks
    result = run(rt, sandbox, ref, "ADVANCED_H")
    assert result.status == "succeeded"
    assert len(rt.store.attempts("alice", result.id)) == 2
    for overrides in (
        WorkloadProfile(input_tokens=4096, output_tokens=128, max_model_calls=1),
        WorkloadProfile(input_tokens=4096, output_tokens=128, max_cost_micro_usd=1),
    ):
        blocked = plan(request.model_copy(update={"overrides": overrides}), catalog)
        assert blocked.status == "blocked"


def test_repair_contract_rejects_unreserved_attempts(rt, sandbox):
    policy = rt.store.policy("alice", sandbox[3].policy).policy
    raw = policy.model_dump()
    raw["stages"][0]["max_repairs"] = 2
    with pytest.raises(ValidationError):
        ExecutablePolicy.model_validate(raw)
    with pytest.raises(ValidationError):
        PlanStage(id="repair", task="coding", max_repairs=1)


def test_routing_quality_confidence_separated(rt, sandbox):
    catalog = sandbox[2]
    request = PreviewRequest(
        description="Keep processing local",
        catalog_id=catalog.id,
        overrides=WorkloadProfile(input_tokens=4096, output_tokens=128, local_only=True),
    )
    stage = plan(request, catalog).stages[0]
    assert stage.routing_confidence == "high"
    assert stage.quality_confidence == stage.confidence == "low"
    assert sum(c.eligible for c in stage.candidates) == 1
    assert (
        "Routing confidence high" in stage.explanation
        and "Model-quality confidence low" in stage.explanation
    )


def test_outcome_rating_http_is_scoped_immutable_and_not_training(rt, sandbox, tmp_path):
    import base64
    import json

    from buildbox_router.api import create_app
    from buildbox_router.auth import password_hash
    from buildbox_router.config import Settings
    from fastapi.testclient import TestClient

    scenario = sandbox[3]
    activate(rt, scenario.policy, scenario.admission_id)
    result = run(rt, sandbox, scenario.policy)
    auth = tmp_path / "synthetic-auth.json"
    auth.write_text(
        json.dumps(
            [
                {
                    "username": name,
                    "owner": name,
                    "salt": "0" * 32,
                    "password_hash": password_hash("synthetic-password", "0" * 32),
                }
                for name in ("alice", "bob")
            ]
        )
    )
    app = create_app(
        Settings(identity_mode="shared", auth_file=str(auth)), sandbox[0], sandbox[1], rt.store
    )

    def headers(owner):
        return {
            "Authorization": "Basic "
            + base64.b64encode(f"{owner}:synthetic-password".encode()).decode()
        }

    path = "/api/studio/intelligence/outcomes"
    with TestClient(app, headers=headers("alice")) as client:
        assert client.get(path).json()[0]["repair_count"] == 1
        assert client.get(path, headers=headers("bob")).json() == []
        assert (
            client.post(
                path + f"/{result.id}/rating", json={"rating": 5}, headers=headers("bob")
            ).status_code
            == 404
        )
        assert client.post(path + f"/{result.id}/rating", json={"rating": 5}).status_code == 200
        assert client.post(path + f"/{result.id}/rating", json={"rating": 5}).status_code == 200
        assert client.post(path + f"/{result.id}/rating", json={"rating": 4}).status_code == 409
        assert client.post(path + f"/{result.id}/rating", json={"rating": 6}).status_code == 422
        value = client.get(path).json()[0]
        assert value["rating"] == 5 and not value["affects_ranking"]
        assert client.get(path, headers={"Authorization": ""}).status_code == 401


def test_repair_exhaustion_does_not_open_provider_circuit(rt, sandbox, loopback):
    from buildbox_router.gateway.health import DeploymentHealth

    scenario = sandbox[3]
    activate(rt, scenario.policy, scenario.admission_id)
    loopback.respond = lambda body: setattr(loopback, "result", wire(content="Incomplete"))
    for _ in range(2):
        assert run(rt, sandbox, scenario.policy).status == "failed"
    assert not DeploymentHealth(rt.store).unavailable("alice", sandbox[2].id)


def test_repair_edit_keeps_bounds_without_reusing_admission(rt, sandbox):
    from buildbox_router.execution_contracts import PolicyEditRequest
    from buildbox_router.execution_policy import edit

    original = rt.store.policy("alice", sandbox[3].policy).policy
    changed = edit(
        original,
        sandbox[2],
        PolicyEditRequest(prompt_templates={"generate": "Correct answer from {{input}}"}),
        sandbox[0].selector,
    )
    assert changed.stages[0].max_repairs == 1
    assert changed.stages[0].budget.max_model_calls == 2
    assert digest(changed) != digest(original)


def test_repair_reserves_slowest_target_independently_of_price(rt, sandbox):
    from .test_advanced_router import changed_fact

    catalog = changed_fact(
        sandbox[2], "advanced-small-loopback", "latency_ms", 2000, basis="synthetic"
    )
    graph = ExecutionPlan(
        stages=(
            PlanStage(
                id="attempt",
                task="coding",
                escalate=True,
                max_repairs=1,
                validators=(ValidationRule(kind="required_terms", values=("VALID",)),),
            ),
        )
    )
    value = plan(
        PreviewRequest(
            description="Solve code",
            catalog_id=catalog.id,
            execution_plan=graph,
            overrides=WorkloadProfile(input_tokens=4096, output_tokens=128, max_attempts=3),
        ),
        catalog,
    )
    stage = value.stages[0]
    used = [c for c in stage.candidates if c.configuration_id in (stage.selected, *stage.fallbacks)]
    assert len(used) == 2 and value.max_model_calls == 3
    latency = [c.metrics["latency"] for c in used]
    assert value.projected_latency_ms == sum(latency) + max(latency)
    policy = compile_policy(value, "repair-budget")
    assert policy.budget.max_cost_micro_usd == value.projected_cost_micro_usd


def test_repair_without_criteria_rejected_at_request_boundary():
    with pytest.raises(ValidationError):
        PreviewRequest(description="Task", catalog_id="catalog", max_repairs=1)
