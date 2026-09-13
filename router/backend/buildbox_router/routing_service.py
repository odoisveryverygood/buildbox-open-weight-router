"""Thin composition of deterministic intelligence and existing versioned stores."""

from collections import Counter
from uuid import uuid4

from .contracts import CatalogSnapshot, ErrorCode, Intake, Interpretation, WorkloadProfile
from .errors import DomainError
from .execution_contracts import ExecutablePolicy, RunAttempt, VersionRef
from .execution_storage import SandboxStorage, append
from .gateway.health import DeploymentHealth
from .intelligence.planner import compile_policy, plan
from .intelligence.workload import override
from .planning_contracts import PlanInput, PlanningResult
from .planning_storage import PlanningStorage
from .routing_contracts import (
    CatalogChange,
    PreviewRequest,
    RouterMetrics,
    RoutingDecision,
    ShadowComparison,
    WhatIfRequest,
)


def save_decision(store: SandboxStorage, tenant: str, decision: RoutingDecision) -> RoutingDecision:
    with store.engine.begin() as conn:
        append(
            conn,
            tenant,
            "router_policy",
            decision.router_policy.id,
            decision.router_policy.version,
            decision.router_policy,
        )
        append(conn, tenant, "routing_decision", decision.id, 1, decision)
    return decision


def preview(
    store: SandboxStorage,
    tenant: str,
    request: PreviewRequest,
    catalog: CatalogSnapshot,
    *,
    profile: WorkloadProfile | None = None,
) -> RoutingDecision:
    return save_decision(
        store,
        tenant,
        plan(
            request,
            catalog,
            profile=profile,
            unhealthy=DeploymentHealth(store).unavailable(tenant, catalog.id),
        ),
    )


def decision(store: SandboxStorage, tenant: str, identifier: str) -> RoutingDecision:
    return RoutingDecision.model_validate_json(store.read(tenant, "routing_decision", identifier))


def what_if(
    store: SandboxStorage, tenant: str, original: RoutingDecision, request: WhatIfRequest
) -> tuple[RoutingDecision, ShadowComparison]:
    profile = override(original.profile, request.overrides)
    new = preview(
        store,
        tenant,
        PreviewRequest(
            description=original.objective,
            catalog_id=original.catalog.id,
            policy=request.policy,
            required_terms=original.required_terms,
            execution_plan=original.execution_plan,
        ),
        original.catalog,
        profile=profile,
    )
    old_pins = {s.node_id: s.selected for s in original.stages}
    changes = tuple(
        f"{s.node_id}: {old_pins.get(s.node_id)} → {s.selected}; objectives/hard constraints recomputed"
        for s in new.stages
        if old_pins.get(s.node_id) != s.selected
    )

    def delta(a: float | None, b: float | None) -> float | None:
        return b - a if a is not None and b is not None else None

    comparison = ShadowComparison(
        authoritative_decision=original.id,
        experimental_decision=new.id,
        disagreements=changes,
        metric_deltas={
            "projected_cost_micro_usd": delta(
                original.projected_cost_micro_usd, new.projected_cost_micro_usd
            ),
            "projected_latency_ms": delta(original.projected_latency_ms, new.projected_latency_ms),
        },
    )
    with store.engine.begin() as conn:
        append(conn, tenant, "shadow_decision", new.id, 1, comparison)
    return new, comparison


def draft(store: SandboxStorage, tenant: str, record: RoutingDecision) -> ExecutablePolicy:
    if record.status != "ready":
        raise DomainError(
            ErrorCode.UNSUPPORTED, "No valid plan satisfies all hard constraints", 422
        )
    policy_id = "route-" + record.id
    if store.policy_exists(tenant, VersionRef(id=policy_id, version=1)):
        return store.policy(tenant, VersionRef(id=policy_id, version=1)).policy
    policy = compile_policy(record, uuid4().hex)
    planning = PlanningStorage(store.engine)
    planning.publish_deterministic(
        tenant,
        PlanInput(
            intake=Intake(
                description=f"{record.profile.task} workload from saved routing decision",
                constraints=policy.workflow.constraints,
            ),
            proposal_mode="single_stage",
        ),
        PlanningResult(
            plan_id=policy.plan.id,
            version=1,
            interpretation=Interpretation(status="ready", workflow=policy.workflow),
            workflow=policy.workflow,
            catalog=record.catalog,
            status="provisional",
            fixture=record.catalog.synthetic,
            assumptions=("Deterministic evidence-based routing; not a model-quality validation",),
        ),
    )
    for prompt in policy.prompts:
        store.save_prompt(tenant, prompt)
    return store.create_policy(tenant, policy).policy


def catalog_diff(before: CatalogSnapshot, after: CatalogSnapshot) -> tuple[CatalogChange, ...]:
    # Field-level snapshots; old snapshots/runs are never modified.
    changes = []
    for group in ("artifacts", "configurations", "eligibility", "intelligence", "performance"):
        key = "configuration_id" if group in ("eligibility", "intelligence") else "id"
        left = {getattr(x, key): x.model_dump(mode="json") for x in getattr(before, group)}
        right = {getattr(x, key): x.model_dump(mode="json") for x in getattr(after, group)}
        for identifier in sorted(left.keys() | right.keys()):
            a, b = left.get(identifier), right.get(identifier)
            for field in sorted((a or {}).keys() | (b or {}).keys()):
                av, bv = (a or {}).get(field), (b or {}).get(field)
                if av != bv:
                    changes.append(
                        CatalogChange(
                            configuration_id=identifier,
                            field=f"{group}.{field}",
                            before=str(av) if av is not None else None,
                            after=str(bv) if bv is not None else None,
                        )
                    )
    return tuple(changes)


def metrics(store: SandboxStorage, tenant: str) -> RouterMetrics:
    decisions = [
        RoutingDecision.model_validate_json(r) for r in store.records(tenant, "routing_decision")
    ]
    attempts = [RunAttempt.model_validate_json(r) for r in store.records(tenant, "attempt")]
    shadows = [
        ShadowComparison.model_validate_json(r) for r in store.records(tenant, "shadow_decision")
    ]
    latencies = [a.latency_ms for a in attempts if a.latency_ms is not None]
    return RouterMetrics(
        coverage="At most 1000 latest records per kind; not a complete billing export",
        synthetic=store.offline_contract_test,
        decisions=len(decisions),
        confidence_distribution=dict(Counter(s.confidence for d in decisions for s in d.stages)),
        configuration_distribution=dict(
            Counter(s.selected for d in decisions for s in d.stages if s.selected)
        ),
        rejection_reasons=dict(
            Counter(
                r for d in decisions for s in d.stages for c in s.candidates for r in c.rejected
            )
        ),
        attempts=len(attempts),
        failure_rate=sum(a.status != "succeeded" for a in attempts) / len(attempts)
        if attempts
        else None,
        fallback_rate=sum(a.attempt > 1 for a in attempts) / len(attempts) if attempts else None,
        average_latency_ms=sum(latencies) / len(latencies) if latencies else None,
        known_cost_micro_usd=sum(a.usage.actual_micro_usd or 0 for a in attempts),
        unknown_cost_attempts=sum(a.usage.actual_micro_usd is None for a in attempts),
        policy_disagreement_rate=sum(bool(s.disagreements) for s in shadows) / len(shadows)
        if shadows
        else None,
    )
