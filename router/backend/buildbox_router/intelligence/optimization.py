"""Task-scoped hard gates, conservative utility and Pareto; no network or dispatch."""

import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal, cast

from pydantic import JsonValue

from ..contracts import (
    Binding,
    CandidateConfiguration,
    Capability,
    CapabilityObservation,
    CatalogSnapshot,
    Constraints,
    Node,
    Provenance,
    TargetRequirements,
    Workflow,
    WorkloadProfile,
)
from ..routing_contracts import CandidateUtility, Objective, RouterPolicy, StageDecision
from .selection.engine import DeterministicSelector


def workflow_for(profile: WorkloadProfile) -> Workflow:
    return Workflow(
        id="preview",
        version=1,
        title="Workload capability check",
        inputs=("input",),
        nodes=(
            Node(
                id="respond",
                kind="llm",
                purpose="Workload stage",
                inputs={"input": Binding(source="input", output="value", from_input=True)},
            ),
        ),
        requirements=TargetRequirements(
            structured_output=profile.structured_output != "text",
            tool_calling="tools" in profile.required,
        ),
        constraints=Constraints(
            provenance=Provenance(kind="user_declared", source="Workload constraints")
        ),
        provenance=Provenance(kind="inference", source="workload-rules-1"),
    )


def observation(
    catalog: CatalogSnapshot, configuration: str, key: Capability, now: datetime
) -> CapabilityObservation | None:
    record = next((v for v in catalog.intelligence if v.configuration_id == configuration), None)
    obs = record.facts.get(key) if record else None
    evidence = {e.id: e for e in catalog.evidence}
    if not obs or not obs.observed_at <= now < obs.expires_at:
        return None
    p = obs.fact.provenance
    if not p.evidence_ids or not set(p.evidence_ids) <= evidence.keys():
        return None
    if not catalog.synthetic and (
        p.kind == "synthetic"
        or any(evidence[i].provenance.kind == "synthetic" for i in p.evidence_ids)
    ):
        return None
    return obs


def quality(
    catalog: CatalogSnapshot, configuration: str, profile: WorkloadProfile, now: datetime
) -> tuple[float | None, str, tuple[str, ...], tuple[str, ...], int | None]:
    evidence = {e.id for e in catalog.evidence}
    comparable = [
        p
        for p in catalog.performance
        if p.task == profile.task
        and p.reviewed
        and p.retrieved_at <= now < p.expires_at
        and p.provenance.evidence_ids
        and set(p.provenance.evidence_ids) <= evidence
        and (catalog.synthetic or p.origin != "synthetic")
    ]
    rows = [p for p in comparable if p.configuration_id == configuration]
    if not rows:
        return None, "unknown", (), (), None
    # Scores from unlike benchmark settings do not become independent votes.
    identities = {
        (
            p.benchmark,
            p.benchmark_version,
            p.split,
            p.harness,
            p.settings,
            p.normalization,
            p.unit,
            p.scale_min,
            p.scale_max,
            p.higher_is_better,
        )
        for p in comparable
    }
    conflict = (
        len(identities) > 1
        or max(p.normalized_score for p in rows) - min(p.normalized_score for p in rows) > 0.000001
    )
    ids = tuple(p.id for p in rows)
    if conflict:
        return (
            None,
            "conflict",
            ids,
            (
                "Conflicting scores or incomparable task-specific benchmark methods across deployments; not averaged",
            ),
            None,
        )
    basis = (
        "synthetic"
        if any(p.origin == "synthetic" for p in rows)
        else "measured"
        if all(p.origin == "internal_evaluation" and p.measured_at is not None for p in rows)
        else "imported"
    )
    sizes = [p.sample_size for p in rows]
    return (
        rows[0].normalized_score,
        basis,
        ids,
        (),
        min(cast(list[int], sizes)) if all(s is not None for s in sizes) else None,
    )


def assess(
    profile: WorkloadProfile,
    catalog: CatalogSnapshot,
    policy: RouterPolicy,
    *,
    now: datetime | None = None,
    unhealthy: set[str] | None = None,
) -> tuple[CandidateUtility, ...]:
    now = now or datetime.now(UTC)
    base = DeterministicSelector().filter(workflow_for(profile), catalog)
    result = []
    for candidate in catalog.configurations:
        rejected = list(base.excluded.get(candidate.id, ()))
        sources: set[str] = set()

        def fact(
            key: Capability,
            *,
            hard: bool = False,
            candidate: CandidateConfiguration = candidate,
            sources: set[str] = sources,
        ) -> JsonValue:
            item = observation(catalog, candidate.id, key, now)
            if item:
                sources.update(item.fact.provenance.evidence_ids)
            if item is None or (hard and item.basis in ("unknown", "estimated")):
                return None
            return item.fact.value

        def require(
            key: Capability,
            predicate: Callable[[Any], bool],
            description: str,
            rejected: list[str] = rejected,
        ) -> None:
            value = fact(key, hard=True)
            if value is None or not predicate(value):
                rejected.append(
                    f"{description}: {'unknown/stale' if value is None else 'contradicted'}"
                )

        for cap in profile.required:
            require(cap, lambda v: v is True, f"required capability {cap}")
        if profile.input_tokens is not None and profile.output_tokens is not None:
            require(
                "context_tokens",
                lambda v: (
                    type(v) in (int, float)
                    and v >= cast(int, profile.input_tokens) + cast(int, profile.output_tokens)
                ),
                "context envelope",
            )
            require(
                "max_output_tokens",
                lambda v: type(v) in (int, float) and v >= profile.output_tokens,
                "output envelope",
            )
        else:
            rejected.append("input/output envelope: unknown; clarification required")
        if profile.local_only:
            require("local", lambda v: v is True, "local-only privacy")
        if profile.self_hosted_only:
            require("self_hosted", lambda v: v is True, "self-hosted deployment")
        if profile.no_retention:
            require("retention_days", lambda v: type(v) in (int, float) and v == 0, "no retention")
        if (
            profile.approved_providers
            and candidate.provider.value not in profile.approved_providers
        ):
            rejected.append("approved-provider allowlist: mismatched or unknown")
        if profile.determinism == "required":
            rejected.append("exact deterministic inference: no supported guarantee")
        if profile.tools and (
            profile.no_external_tools or len(profile.tools) > profile.max_tool_calls
        ):
            rejected.append("tool policy: explicit authorized workflow tool plan required")
        if candidate.id in (unhealthy or set()):
            rejected.append("deployment circuit open: recent observed failures")
        metrics: dict[Objective, float | None] = {}
        bases: dict[Objective, str] = {}
        for metric, key in (
            ("latency", "latency_ms"),
            ("throughput", "throughput_tokens_s"),
            ("reliability", "success_rate"),
        ):
            item = observation(catalog, candidate.id, cast(Capability, key), now)
            val = fact(cast(Capability, key))
            metrics[cast(Objective, metric)] = (
                float(cast(float, val)) if type(val) in (int, float) else None
            )
            bases[cast(Objective, metric)] = item.basis if item else "unknown"
        prices = [
            fact(cast(Capability, k), hard=True)
            for k in ("input_usd_per_million", "output_usd_per_million", "request_usd")
        ]
        cost = None
        if (
            all(type(p) in (int, float) for p in prices)
            and profile.input_tokens is not None
            and profile.output_tokens is not None
        ):
            cost = (
                float(cast(float, prices[0])) * profile.input_tokens
                + float(cast(float, prices[1])) * profile.output_tokens
                + float(cast(float, prices[2])) * 1000000
            )
        metrics["cost"], bases["cost"] = (
            cost,
            "synthetic estimate"
            if catalog.synthetic
            else "estimated from declared component prices",
        )
        if profile.max_cost_micro_usd is not None and (
            cost is None or cost > profile.max_cost_micro_usd
        ):
            rejected.append("hard workflow cost: unknown or exceeded")
        if profile.max_latency_ms is not None:
            require(
                "latency_ms",
                lambda v: type(v) in (int, float) and v <= profile.max_latency_ms,
                "latency ceiling",
            )
        q, basis, ids, conflicts, _ = quality(catalog, candidate.id, profile, now)
        metrics["quality"], bases["quality"] = q, basis
        if profile.min_quality is not None and (q is None or q < profile.min_quality):
            rejected.append("minimum task-specific expected quality: unknown or insufficient")
        sources.update(ids)
        local, hosted = fact("local"), fact("self_hosted")
        metrics["privacy"] = (
            1.0
            if local is True
            else 0.75
            if hosted is True
            else 0.0
            if local is False and hosted is False
            else None
        )
        bases["privacy"] = "synthetic" if catalog.synthetic else "declared"
        optional = [fact(k) for k in profile.optional]
        metrics["capability"] = (
            sum(v is True for v in optional) / len(optional)
            if optional and all(v is not None for v in optional)
            else None
            if optional
            else 1.0
        )
        bases["capability"] = "synthetic" if catalog.synthetic else "declared"
        result.append(
            CandidateUtility(
                configuration_id=candidate.id,
                eligible=not rejected,
                rejected=tuple(rejected),
                metrics=metrics,
                metric_basis=bases,
                evidence_ids=tuple(sorted(sources)),
                unknown=tuple(k for k in policy.weights if metrics.get(k) is None),
                conflicts=conflicts,
            )
        )
    return tuple(result)


def rank(rows: tuple[CandidateUtility, ...], policy: RouterPolicy) -> tuple[CandidateUtility, ...]:
    eligible = [r for r in rows if r.eligible]
    weights = {k: v / sum(policy.weights.values()) for k, v in policy.weights.items() if v > 0}
    scored = []
    for row in rows:
        if not row.eligible:
            scored.append(row)
            continue
        normalized: dict[Objective, float] = {}
        for metric in weights:
            value = row.metrics.get(metric)
            available = [v for r in eligible if (v := r.metrics.get(metric)) is not None]
            if value is None or not available:
                normalized[metric] = -policy.unknown_penalty - 0.001
                continue
            low, high = min(available), max(available)
            assert low is not None and high is not None
            n = 1.0 if high == low else (value - low) / (high - low)
            if metric in ("latency", "cost") and high != low:
                n = 1 - n
            if row.metric_basis.get(metric) == "estimated":
                n *= 1 - policy.estimated_discount
            normalized[metric] = n

        # Pareto compares known raw metrics only; unknown never dominates known.
        def dominates(other: CandidateUtility, row: CandidateUtility = row) -> bool:
            strict = False
            for metric in weights:
                a, b = other.metrics.get(metric), row.metrics.get(metric)
                if a is None:
                    if b is not None:
                        return False
                    continue
                if b is None:
                    strict = True
                    continue
                delta = b - a if metric in ("cost", "latency") else a - b
                if delta < 0:
                    return False
                strict |= delta > 0
            return strict

        scored.append(
            row.model_copy(
                update={
                    "normalized": normalized,
                    "utility": sum(weights[k] * v for k, v in normalized.items()),
                    "pareto": not any(
                        other.configuration_id != row.configuration_id and dominates(other)
                        for other in eligible
                    ),
                }
            )
        )
    return tuple(
        sorted(
            scored,
            key=lambda r: (
                not r.eligible,
                -(r.utility if r.utility is not None else -math.inf),
                r.configuration_id,
            ),
        )
    )


def select(
    profile: WorkloadProfile,
    catalog: CatalogSnapshot,
    policy: RouterPolicy,
    node_id: str,
    depends_on: tuple[str, ...] = (),
    *,
    now: datetime | None = None,
    unhealthy: set[str] | None = None,
) -> StageDecision:
    now = now or datetime.now(UTC)
    rows = rank(assess(profile, catalog, policy, now=now, unhealthy=unhealthy), policy)
    eligible = [r for r in rows if r.eligible]
    winner = eligible[0] if eligible else None
    uncertainty = []
    confidence: Literal["low", "medium", "high"] = "low"
    if winner:
        missing_quality = sum(r.metrics.get("quality") is None for r in eligible)
        if missing_quality:
            uncertainty.append(
                f"No comparable task-quality evidence for {missing_quality} of {len(eligible)} eligible deployments"
            )
        if winner.unknown:
            uncertainty.append(
                "Selected deployment has unknown objectives: " + ", ".join(winner.unknown)
            )
        gap = (
            cast(float, winner.utility) - cast(float, eligible[1].utility)
            if len(eligible) > 1
            else 1.0
        )
        _, basis, _, _, samples = quality(catalog, winner.configuration_id, profile, now)
        if gap < policy.clear_margin:
            uncertainty.append("Eligible utilities are close under this policy")
        if catalog.synthetic:
            uncertainty.append("Synthetic evidence tests routing behavior, not model quality")
        elif (
            not winner.unknown
            and not missing_quality
            and basis == "measured"
            and samples
            and samples >= policy.minimum_samples
        ):
            confidence = "high" if gap >= policy.clear_margin else "medium"
        else:
            uncertainty.append("Insufficient measured sample coverage for high confidence")
    else:
        uncertainty.append("No eligible deployment remains")
    tradeoffs = []
    if winner and len(eligible) > 1:
        other = eligible[1]
        for metric, label, unit in (
            ("cost", "projected cost", "micro-USD"),
            ("latency", "expected latency", "ms"),
        ):
            a, b = (
                winner.metrics.get(cast(Objective, metric)),
                other.metrics.get(cast(Objective, metric)),
            )
            if a is not None and b is not None:
                tradeoffs.append(f"{label} {a - b:+.3f} {unit} versus {other.configuration_id}")
    explanation = (
        f"Understood {profile.task}; required {', '.join(profile.required)}. "
        f"Rejected {len(rows) - len(eligible)} of {len(rows)} deployments by hard constraints. "
        + (
            f"Selected {winner.configuration_id} from {len(eligible)} eligible deployments using normalized {', '.join(k for k, v in policy.weights.items() if v)} utility; {sum(r.pareto for r in rows)} Pareto-efficient alternatives. "
            f"Tradeoff follows {policy.id}@{policy.version}; changing weights, hard limits or reviewed task evidence can change the decision. "
            if winner
            else "No valid plan satisfies all hard constraints. "
        )
        + ("Known tradeoff: " + "; ".join(tradeoffs) + ". " if tradeoffs else "")
        + f"Confidence {confidence}: "
        + "; ".join(uncertainty or ["measured task evidence and a clear utility margin"])
    )
    return StageDecision(
        node_id=node_id,
        depends_on=depends_on,
        profile=profile,
        selected=winner.configuration_id if winner else None,
        candidates=rows,
        confidence=confidence,
        uncertainty=tuple(uncertainty),
        explanation=explanation,
    )
