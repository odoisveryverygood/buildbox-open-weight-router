import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from buildbox_router.composition import product_services
from buildbox_router.contracts import (
    CapabilityObservation,
    DeploymentIntelligence,
    Fact,
    PerformanceEvidence,
    WorkloadProfile,
)
from buildbox_router.errors import DomainError
from buildbox_router.execution_composition import compose_execution
from buildbox_router.execution_contracts import (
    ChatCompletionRequest,
    ChatMessage,
    CircuitPolicy,
    PolicyEditRequest,
    RouteAlias,
    TransitionRequest,
    ValidationRule,
    VersionRef,
    WorkflowRunRequest,
    digest,
)
from buildbox_router.execution_policy import edit
from buildbox_router.execution_storage import append
from buildbox_router.gateway.health import DeploymentHealth
from buildbox_router.intelligence.optimization import assess, quality, rank, select
from buildbox_router.intelligence.planner import catalog_digest, compile_policy, plan
from buildbox_router.intelligence.workload import analyze
from buildbox_router.planning_storage import PlanningStorage
from buildbox_router.research.fixture import SyntheticCatalog
from buildbox_router.routing_contracts import (
    PreviewRequest,
    RouterPolicy,
    WhatIfRequest,
    WorkloadRequest,
)
from buildbox_router.routing_service import catalog_diff, decision, draft, preview, what_if
from buildbox_router.validators import validate_rules
from buildbox_router.worker import run_once
from pydantic import ValidationError

from .advanced_setup import advanced_catalog, scenario_requests, setup_advanced
from .conftest import ctx
from .stakeholder_setup import setup_demo
from .test_unblock import loopback as loopback


@pytest.fixture
def catalog():
    return advanced_catalog(SyntheticCatalog().snapshot())


def profile(**changes):
    return WorkloadProfile(input_tokens=4096, output_tokens=128, **changes)


def changed_fact(catalog, name, key, value=None, *, basis="unknown", expires=False):
    record = next(r for r in catalog.intelligence if r.configuration_id == name)
    original = record.facts[key]
    p = original.fact.provenance
    if basis == "estimated":
        p = p.model_copy(update={"kind": "inference"})
    fact = Fact(
        value=value, provenance=p, unknown_reason="Unknown fixture field" if value is None else None
    )
    modified = original.model_copy(
        update={
            "fact": fact,
            "basis": basis,
            **(
                {
                    "observed_at": datetime.now(UTC) - timedelta(days=2),
                    "expires_at": datetime.now(UTC) - timedelta(seconds=1),
                }
                if expires
                else {}
            ),
        }
    )
    record = record.model_copy(update={"facts": record.facts | {key: modified}})
    return catalog.model_copy(
        update={
            "intelligence": tuple(
                record if r.configuration_id == name else r for r in catalog.intelligence
            )
        }
    )


def test_workload_rules_explicit_override_and_no_private_prose():
    value = analyze(
        WorkloadRequest(
            description="SECRET_CLIENT summarize locally with schema JSON",
            overrides=WorkloadProfile(
                task="coding", local_only=False, input_tokens=1000, output_tokens=100
            ),
        )
    )
    assert value.task == "coding" and not value.local_only
    assert value.structured_output == "schema_json" and "schema_json" in value.required
    assert "SECRET_CLIENT" not in value.model_dump_json()
    assert value.evidence["task"] == "explicit user override"


@pytest.mark.parametrize(
    "phrase,task",
    [
        ("summarize notes", "summarization"),
        ("debug a stack trace", "debugging"),
        ("classify receipt", "classification"),
        ("scientific reasoning", "science"),
        ("mathematical theorem", "mathematics"),
        ("translate text", "multilingual"),
        ("image reasoning", "vision"),
        ("research sources", "research"),
    ],
)
def test_task_families(phrase, task):
    assert analyze(WorkloadRequest(description=phrase)).task == task


@pytest.mark.parametrize("key", ["schema_json", "context_tokens", "local", "retention_days"])
def test_unknown_hard_facts_fail_closed(catalog, key):
    candidate = "advanced-medium-loopback"
    modified = changed_fact(catalog, candidate, key)
    value = profile(
        required=("schema_json",), local_only=key == "local", no_retention=key == "retention_days"
    )
    row = next(
        r
        for r in assess(value, modified, RouterPolicy(weights={"cost": 1}))
        if r.configuration_id == candidate
    )
    assert not row.eligible and any("unknown" in reason for reason in row.rejected)


def test_capability_overrides_price_and_score(catalog):
    result = select(
        profile(required=("schema_json",)), catalog, RouterPolicy(weights={"cost": 1}), "respond"
    )
    assert result.selected != "advanced-small-loopback"
    assert not next(
        r for r in result.candidates if r.configuration_id == "advanced-small-loopback"
    ).eligible


def test_context_privacy_and_hard_budget(catalog):
    requests = scenario_requests(catalog.id)
    decisions = {i: plan(v, catalog) for i, _, v in requests}
    assert decisions["D"].stages[0].selected != "advanced-small-loopback"
    assert decisions["E"].stages[0].selected == "advanced-small-loopback"
    assert decisions["F"].stages[0].selected == "advanced-small-loopback"
    denied = plan(
        requests[0][2].model_copy(update={"overrides": profile(max_cost_micro_usd=0)}), catalog
    )
    assert denied.status == "blocked"


def test_normalization_and_unknown_never_automatically_wins(catalog):
    rows = assess(profile(task="coding"), catalog, RouterPolicy(weights={"latency": 1}))
    ranked = rank(rows, RouterPolicy(weights={"latency": 1}))
    assert ranked[0].configuration_id == "advanced-small-loopback"
    assert all(-1.001 <= r.utility <= 1 for r in ranked if r.eligible)
    changed = changed_fact(catalog, "advanced-small-loopback", "latency_ms")
    assert (
        select(profile(), changed, RouterPolicy(weights={"latency": 1}), "respond").selected
        != "advanced-small-loopback"
    )


def test_pareto_and_confidence_are_evidence_derived(catalog):
    result = select(
        profile(task="coding"),
        catalog,
        RouterPolicy(weights={"quality": 0.5, "cost": 0.5}),
        "respond",
    )
    assert sum(r.pareto for r in result.candidates) >= 2
    assert result.confidence == "low" and "Synthetic" in " ".join(result.uncertainty)
    assert result.selected in result.explanation
    assert f"Rejected {sum(not r.eligible for r in result.candidates)}" in result.explanation


def test_benchmark_scope_conflicts_dates(catalog):
    p = profile(task="science")
    assert quality(catalog, "advanced-small-loopback", p, datetime.now(UTC))[0] is None
    evidence = next(e for e in catalog.performance if e.task == "coding")
    conflicting = evidence.model_copy(
        update={"id": "conflicting-evidence", "normalized_score": 0.99}
    )
    modified = catalog.model_copy(update={"performance": catalog.performance + (conflicting,)})
    q, basis, _, conflicts, _ = quality(
        modified, evidence.configuration_id, profile(task="coding"), datetime.now(UTC)
    )
    assert q is None and basis == "conflict" and conflicts
    assert evidence.measured_at is None


def test_expired_and_estimated_hard_claims_block(catalog):
    for stale in (True, False):
        modified = changed_fact(
            catalog,
            "advanced-medium-loopback",
            "context_tokens",
            100000,
            basis="synthetic" if stale else "estimated",
            expires=stale,
        )
        row = next(
            r
            for r in assess(profile(), modified, RouterPolicy())
            if r.configuration_id == "advanced-medium-loopback"
        )
        assert not row.eligible


@pytest.mark.parametrize(
    "strategy,waves,calls",
    [
        ("single", 1, 1),
        ("multi_stage", 3, 3),
        ("parallel", 2, 4),
        ("generate_verify", 2, 2),
        ("cheap_first", 1, 2),
    ],
)
def test_plan_strategies_compile_existing_typed_dag(catalog, strategy, waves, calls):
    request = PreviewRequest(
        description="Implement code",
        catalog_id=catalog.id,
        policy=RouterPolicy(id="quality", weights={"quality": 1}),
        overrides=profile(task="coding", strategy=strategy),
        required_terms=("VALID",) if strategy == "cheap_first" else (),
    )
    value = plan(request, catalog)
    assert (
        value.status == "ready"
        and len(value.parallel_waves) == waves
        and value.max_model_calls == calls
    )
    policy = compile_policy(value, "saved-plan")
    assert policy.routing_decision_id == value.id and policy.catalog_digest == catalog_digest(
        catalog
    )
    if strategy == "multi_stage":
        assert len({s.selected for s in value.stages}) == 2
    if strategy == "parallel":
        assert len(value.parallel_waves[0]) == 3 and len(policy.workflow.nodes[-1].depends_on) == 3


def test_plan_budget_and_determinism_block(catalog):
    for override in (
        profile(strategy="parallel", max_model_calls=2),
        profile(determinism="required"),
        profile(strategy="cheap_first"),
        profile(data_class="restricted"),
    ):
        result = plan(
            PreviewRequest(description="Task", catalog_id=catalog.id, overrides=override), catalog
        )
        assert result.status == "blocked"
        with pytest.raises(ValueError):
            compile_policy(result, "plan")


def test_shadow_what_if_and_immutable_catalog(rt, catalog):
    original = preview(
        rt.store,
        "alice",
        PreviewRequest(
            description="Implement function",
            catalog_id=catalog.id,
            policy=RouterPolicy(id="speed", weights={"latency": 1}),
            overrides=profile(task="coding"),
        ),
        catalog,
    )
    new, shadow = what_if(
        rt.store,
        "alice",
        original,
        WhatIfRequest(policy=RouterPolicy(id="quality", weights={"quality": 1})),
    )
    assert shadow.disagreements and shadow.executes_models is False
    assert decision(rt.store, "alice", original.id) == original
    assert new.catalog == original.catalog and not rt.inference.calls
    with pytest.raises(DomainError):
        decision(rt.store, "bob", original.id)
    with pytest.raises(DomainError):
        preview(
            rt.store,
            "alice",
            PreviewRequest(
                description="Same version changed",
                catalog_id=catalog.id,
                policy=RouterPolicy(id="speed", weights={"cost": 1}),
                overrides=profile(),
            ),
            catalog,
        )
    changed = changed_fact(catalog, "advanced-small-loopback", "latency_ms", 999, basis="synthetic")
    assert catalog_diff(catalog, changed) and original.catalog_digest != catalog_digest(changed)


def test_circuit_scoped_recovery_and_atomic_probe(rt):
    health = DeploymentHealth(rt.store)
    p = CircuitPolicy(failures=2, cooldown_seconds=10)
    assert health.acquire("alice", "deployment-a", "cat", p, now=100)
    for _ in range(2):
        health.observe("alice", "deployment-a", "cat", p, failure="timeout", latency_ms=2, now=100)
    assert not health.acquire("alice", "deployment-a", "cat", p, now=101)
    assert health.acquire("bob", "deployment-a", "cat", p, now=101)
    assert health.acquire("alice", "deployment-b", "cat", p, now=101)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: health.acquire("alice", "deployment-a", "cat", p, now=111), range(4))
        )
    assert sum(results) == 1
    health.observe("alice", "deployment-a", "cat", p, failure=None, latency_ms=1, now=112)
    assert not health.unavailable("alice", "cat", now=112)


@pytest.mark.parametrize(
    "rule,text,expected",
    [
        (ValidationRule(kind="required_terms", values=("OK",)), "missing", False),
        (ValidationRule(kind="python_syntax"), "def broken(:", False),
        (ValidationRule(kind="python_syntax"), "print('no execution')", True),
        (
            ValidationRule(kind="citation_allowlist", values=("https://example.org/a",)),
            "https://evil.example/a",
            False,
        ),
    ],
)
def test_modular_validators_never_execute(rule, text, expected):
    assert validate_rules(text, (rule,))[0].passed is expected


def test_unknown_not_false_and_nonfinite_rejected(catalog):
    obs = catalog.intelligence[0].facts["local"]
    with pytest.raises(ValidationError):
        CapabilityObservation.model_validate(obs.model_dump() | {"basis": "unknown"})
    bad = obs.model_copy(update={"fact": Fact(value=float("nan"), provenance=obs.fact.provenance)})
    with pytest.raises(ValidationError):
        DeploymentIntelligence(configuration_id="test", facts={"latency_ms": bad})


def test_advanced_scenarios_real_worker_and_validation_escalation(rt, loopback, monkeypatch):
    services = product_services(PlanningStorage(rt.store.engine))
    manifest = setup_demo(rt, loopback, services)
    catalogs, scenarios = setup_advanced(rt, loopback, services, manifest)
    execution = compose_execution(
        rt.store, loopback.registry, services.selector, retention_seconds=60
    )
    failures = []
    stage = execution.workflows.runner._stage

    async def observed_stage(*args, **kwargs):
        try:
            return await stage(*args, **kwargs)
        except Exception as error:
            failures.append(str(error))
            raise

    monkeypatch.setattr(execution.workflows.runner, "_stage", observed_stage)
    for scenario in scenarios:
        policy = rt.store.policy("alice", scenario.policy).policy
        rt.store.transition(
            "alice",
            scenario.policy,
            TransitionRequest(
                expected_sequence=1, status="sandbox_enabled", admission_id=scenario.admission_id
            ),
        )
        run = asyncio.run(
            execution.workflows.submit(
                ctx(), WorkflowRunRequest(policy=scenario.policy, inputs={"input": scenario.input})
            )
        )
        assert run_once(services, execution=execution)
        result = asyncio.run(execution.workflows.get(ctx(), run.id))
        assert result.status == "succeeded", (
            failures,
            scenario.id,
            result,
            rt.store.attempts("alice", run.id),
        )
        attempts = rt.store.attempts("alice", run.id)
        assert all(a.trace.routing_decision_id == policy.routing_decision_id for a in attempts)
        if scenario.id == "H":
            assert len(attempts) == 2 and any(
                a.failure_kind == "quality_validation" for a in attempts
            )
            assert any(a.validation and not a.validation[0].passed for a in attempts)
            assert any(a.fallback_reason == "quality_validation" for a in attempts)
        if scenario.id == "I":
            assert all(a.trace.configuration_id != "health-medium-loopback" for a in attempts)
        if scenario.id == "G":
            assert len(attempts) == 3 and len({a.trace.configuration_id for a in attempts}) == 2


def test_performance_normalization_cannot_be_invented(catalog):
    row = catalog.performance[0]
    with pytest.raises(ValidationError):
        PerformanceEvidence.model_validate(row.model_dump() | {"normalized_score": 0.01})


def test_cross_model_incomparable_benchmarks_are_unknown(catalog):
    evidence = next(e for e in catalog.performance if e.task == "coding")
    modified = catalog.model_copy(
        update={
            "performance": tuple(
                e.model_copy(update={"benchmark_version": "incomparable-v2"})
                if e.id == evidence.id
                else e
                for e in catalog.performance
            )
        }
    )
    value = select(
        profile(task="coding"), modified, RouterPolicy(weights={"quality": 1}), "respond"
    )
    assert all(c.metrics.get("quality") is None for c in value.candidates)
    assert value.confidence == "low"


def test_explanation_tradeoffs_match_actual_metrics(catalog):
    value = select(profile(task="coding"), catalog, RouterPolicy(weights={"quality": 1}), "respond")
    first, second = [c for c in value.candidates if c.eligible][:2]
    difference = first.metrics["cost"] - second.metrics["cost"]
    assert f"{difference:+.3f} micro-USD versus {second.configuration_id}" in value.explanation


@pytest.mark.parametrize(
    "samples,margin,expected", [(40, 0.1, "high"), (40, 0.9, "medium"), (2, 0.1, "low")]
)
def test_confidence_threshold_logic_with_explicit_unit_stubs(
    catalog, monkeypatch, samples, margin, expected
):
    # Pure confidence branch coverage; these stubs are NOT public/measurement records.
    from buildbox_router.intelligence import optimization

    policy = RouterPolicy(weights={"cost": 1}, clear_margin=margin)
    rows = assess(profile(task="coding"), catalog, policy)
    monkeypatch.setattr(optimization, "assess", lambda *args, **kwargs: rows)
    monkeypatch.setattr(optimization, "quality", lambda *args: (0.5, "measured", (), (), samples))
    result = optimization.select(
        profile(task="coding"), catalog.model_copy(update={"synthetic": False}), policy, "respond"
    )
    assert (
        result.confidence == expected
        and f"Model-quality confidence {expected}" in result.explanation
    )
    assert result.quality_confidence == expected


def test_objective_preserved_without_template_injection(catalog):
    value = plan(
        PreviewRequest(
            description="Extract ONLY invoice dates {{secret}}",
            catalog_id=catalog.id,
            overrides=profile(),
        ),
        catalog,
    )
    policy = compile_policy(value, "objective-plan")
    assert "Extract ONLY invoice dates" in policy.prompts[0].template
    assert "secret" not in policy.prompts[0].variables


def test_manual_pin_rechecks_advanced_privacy_and_clears_winner_claim(catalog):
    value = plan(
        PreviewRequest(
            description="Summarize locally",
            catalog_id=catalog.id,
            overrides=profile(local_only=True),
        ),
        catalog,
    )
    policy = compile_policy(value, "private-plan")
    from buildbox_router.intelligence.selection.engine import DeterministicSelector

    selector = DeterministicSelector()
    with pytest.raises(DomainError):
        edit(
            policy,
            catalog,
            PolicyEditRequest(pins={"respond": "advanced-medium-loopback"}),
            selector,
        )
    changed = edit(
        policy,
        catalog,
        PolicyEditRequest(prompt_templates={"respond": "New prompt {{input}}"}),
        selector,
    )
    assert changed.version == 2 and changed.routing_decision_id is None
    assert policy.routing_decision_id == value.id


def test_unknown_prices_cannot_produce_executable_ready(catalog):
    for config in catalog.configurations:
        catalog = changed_fact(catalog, config.id, "request_usd")
    value = plan(
        PreviewRequest(description="Summarize", catalog_id=catalog.id, overrides=profile()), catalog
    )
    assert value.status == "blocked" and value.projected_cost_micro_usd is None


@pytest.mark.parametrize("strategy,expected", [("parallel", 4), ("generate_verify", 2)])
def test_advanced_dags_execute_on_existing_worker(rt, loopback, strategy, expected):
    services = product_services(PlanningStorage(rt.store.engine))
    manifest = setup_demo(rt, loopback, services)
    catalogs, _ = setup_advanced(rt, loopback, services, manifest)
    record = preview(
        rt.store,
        "alice",
        PreviewRequest(
            description="Review code independently",
            catalog_id=catalogs[0].id,
            overrides=profile(task="coding", strategy=strategy),
        ),
        catalogs[0],
    )
    policy = draft(rt.store, "alice", record)
    ref = VersionRef(id=policy.id, version=1)
    admission = rt.admission.model_copy(
        update={
            "id": strategy + "-admit",
            "policy": ref,
            "policy_digest": digest(policy),
            "configuration_ids": tuple(dict.fromkeys(s.configuration_id for s in policy.stages)),
        }
    )
    with rt.store.engine.begin() as conn:
        append(conn, "alice", "admission", admission.id, 1, admission)
    rt.store.transition(
        "alice",
        ref,
        TransitionRequest(expected_sequence=1, status="sandbox_enabled", admission_id=admission.id),
    )
    execution = compose_execution(
        rt.store, loopback.registry, services.selector, retention_seconds=60
    )
    run = asyncio.run(
        execution.workflows.submit(
            ctx(), WorkflowRunRequest(policy=ref, inputs={"input": "ADVANCED_parallel public code"})
        )
    )
    assert run_once(services, execution=execution)
    assert asyncio.run(execution.workflows.get(ctx(), run.id)).status == "succeeded"
    outputs = rt.store.outputs_for_run("alice", run.id)
    assert len(outputs) == expected and len(rt.store.attempts("alice", run.id)) == expected
    # The final call contains predecessor outputs, not a secretly separate fake path.
    assert "VALID: synthetic stage result" in str(loopback.seen[-1]["messages"])


def test_post_output_validator_rejects_stream_before_upstream(rt, loopback):
    services = product_services(PlanningStorage(rt.store.engine))
    manifest = setup_demo(rt, loopback, services)
    _, scenarios = setup_advanced(rt, loopback, services, manifest)
    scenario = next(s for s in scenarios if s.id == "H")
    rt.store.transition(
        "alice",
        scenario.policy,
        TransitionRequest(
            expected_sequence=1, status="sandbox_enabled", admission_id=scenario.admission_id
        ),
    )
    policy = rt.store.policy("alice", scenario.policy).policy
    rt.store.create_alias(
        "alice",
        RouteAlias(
            id="validator-stream",
            policy=scenario.policy,
            node_id="respond",
            configuration_id=policy.stages[0].configuration_id,
            created_at=datetime.now(UTC),
        ),
    )
    execution = compose_execution(
        rt.store, loopback.registry, services.selector, retention_seconds=60
    )
    before = len(loopback.seen)

    async def stream():
        async for _ in execution.gateway.stream(
            ctx(),
            ChatCompletionRequest(
                model="validator-stream",
                messages=(ChatMessage(role="user", content="ADVANCED_H"),),
                stream=True,
                max_tokens=128,
            ),
        ):
            pass

    with pytest.raises(DomainError):
        asyncio.run(stream())
    assert len(loopback.seen) == before


def test_intelligence_http_scope_what_if_and_no_activation(rt, loopback):
    import base64

    from fastapi.testclient import TestClient

    from .test_stakeholder_demo import composed

    services, _, app, manifest = composed(rt, loopback)
    catalogs, scenarios = setup_advanced(rt, loopback, services, manifest)
    app.state.intelligence_catalogs = {"alice": {c.id: c for c in catalogs}}
    app.state.advanced_scenarios = scenarios
    headers = {
        "Authorization": "Basic " + base64.b64encode(b"fixture:synthetic-test-password").decode()
    }
    root = "/api/studio/intelligence"
    with TestClient(app, headers=headers) as client:
        assert client.get(root + "/status").status_code == 200
        original = next(s for s in scenarios if s.id == "J")
        before = len(loopback.seen)
        payload = {"policy": {"id": "quality", "weights": {"quality": 1}}}
        changed = client.post(root + f"/decisions/{original.decision_id}/what-if", json=payload)
        assert changed.status_code == 200, changed.text
        assert changed.json()["stages"][0]["selected"] != "advanced-small-loopback"
        assert changed.json()["activation_authority"] is False
        new = client.post(root + "/drafts", json={"decision_id": changed.json()["id"]}).json()
        denied = client.post(
            f"/api/studio/policies/{new['id']}/versions/1/transitions",
            json={
                "expected_sequence": 1,
                "status": "sandbox_enabled",
                "admission_id": original.admission_id,
            },
        )
        assert denied.status_code == 403
        assert (
            client.get(root + f"/decisions/{original.decision_id}").json()["stages"][0]["selected"]
            == "advanced-small-loopback"
        )
        report = client.post(
            root + "/evaluate",
            json={"decisions": [original.decision_id], "experimental": payload["policy"]},
        )
        assert report.status_code == 200 and report.json()["model_quality_conclusion"] is False
        assert (
            client.post(
                root + "/preview", json={"description": "private text", "catalog_id": "unowned"}
            ).status_code
            == 404
        )
        assert client.get(root + "/metrics").json()["attempts"] == 0
        assert len(loopback.seen) == before
        assert client.get(root + "/status", headers={"Authorization": ""}).status_code == 401
