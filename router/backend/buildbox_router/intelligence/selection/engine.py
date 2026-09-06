"""Selection rules 1.0: evidence-gated eligibility, then ordinal cost/complexity.

Facts are canonical Fact[bool]: true=supported, false=contradicted, null=unknown.
No new wire schema is introduced. Missing typed fields are explicit blockers,
not inferred from evidence prose or smuggled through unstructured metadata.
"""

import itertools
import math
import re

from ...contracts import (
    Assignment,
    CandidateConfiguration,
    CatalogSnapshot,
    ErrorCode,
    Fact,
    FilterResult,
    Provenance,
    Recommendation,
    StackComparison,
    Workflow,
)
from ...errors import DomainError

RULE_VERSION = "selection-1.0"
UNREPRESENTED = (
    "context window",
    "output token",
    "commercial license",
    "license policy",
    "zero retention",
    "on-prem",
    "on prem",
    "air-gapped",
    "gpu memory",
    "hardware fit",
    "monthly budget",
    "per workflow budget",
    "per document budget",
)


def _decision(rule: str, value: bool | None, sources: tuple[str, ...], reason: str) -> Fact[bool]:
    return Fact[bool](
        value=value,
        provenance=Provenance(
            kind="inference",
            source=f"{RULE_VERSION}:{rule}",
            evidence_ids=tuple(sorted(set(sources))),
        ),
        unknown_reason=reason if value is None else None,
    )


def _source_valid(fact: Fact[bool] | Fact[float] | Fact[str], catalog: CatalogSnapshot) -> bool:
    evidence = {e.id: e for e in catalog.evidence}
    ids = fact.provenance.evidence_ids
    if not ids or any(i not in evidence for i in ids):
        return False
    if catalog.synthetic:
        return fact.provenance.kind in ("synthetic", "observed", "documented")
    return fact.provenance.kind in ("observed", "documented") and all(
        evidence[i].provenance.kind in ("observed", "documented") for i in ids
    )


class DeterministicSelector:
    def __init__(
        self, *, max_candidates: int = 8, max_mappings: int = 4096, max_model_nodes: int = 8
    ) -> None:
        if not (
            1 <= max_candidates <= 12 and 1 <= max_mappings <= 100000 and 1 <= max_model_nodes <= 10
        ):
            raise ValueError("Selection search bounds outside supported limits")
        self.max_candidates = max_candidates
        self.max_mappings = max_mappings
        self.max_model_nodes = max_model_nodes

    def assess(
        self, workflow: Workflow, catalog: CatalogSnapshot
    ) -> dict[str, tuple[Fact[bool], ...]]:
        workflow = Workflow.model_validate_json(workflow.model_dump_json())
        catalog = CatalogSnapshot.model_validate_json(catalog.model_dump_json())
        artifacts = {a.id: a for a in catalog.artifacts}
        result: dict[str, tuple[Fact[bool], ...]] = {}
        prose = " ".join([workflow.title, *(n.purpose for n in workflow.nodes)]).lower()
        for candidate in sorted(catalog.configurations, key=lambda c: c.id):
            artifact = artifacts[candidate.artifact_id]
            checks: list[Fact[bool]] = []
            weight = artifact.open_weight
            checks.append(
                _decision(
                    "open_weight",
                    weight.value
                    if weight.value is not None and _source_valid(weight, catalog)
                    else None,
                    weight.provenance.evidence_ids,
                    "Open-weight evidence is missing, unresolved or only inferred",
                )
            )
            if not catalog.synthetic:
                checks.append(
                    _decision(
                        "artifact_download_and_legal_scope",
                        None,
                        artifact.provenance.evidence_ids,
                        "v1 lacks exact download verification and contextual license-policy fields; a listing is not verified weights or legal suitability",
                    )
                )
            for rule, fact, ceiling in (
                (
                    "cost_ceiling",
                    candidate.cost_per_1k_tokens,
                    workflow.constraints.max_cost_per_1k_tokens,
                ),
                ("latency_ceiling", candidate.latency_ms, workflow.constraints.max_latency_ms),
            ):
                if ceiling is not None:
                    value = fact.value
                    established = (
                        value is not None
                        and math.isfinite(value)
                        and value >= 0
                        and _source_valid(fact, catalog)
                    )
                    checks.append(
                        _decision(
                            rule,
                            value <= ceiling if established and value is not None else None,
                            fact.provenance.evidence_ids,
                            f"Mandatory {rule} evidence unavailable/invalid; unknown is not zero",
                        )
                    )
            if workflow.constraints.required_region is not None:
                region = candidate.region
                checks.append(
                    _decision(
                        "region",
                        region.value == workflow.constraints.required_region
                        if region.value is not None and _source_valid(region, catalog)
                        else None,
                        region.provenance.evidence_ids,
                        "Required region is not established; region alone does not establish privacy or retention",
                    )
                )
            if any(
                n.kind == "bounded_agent"
                or (
                    n.kind == "llm"
                    and re.search(r"\bjson\b|structured output|tool.call", n.purpose, re.IGNORECASE)
                )
                for n in workflow.nodes
            ):
                checks.append(
                    _decision(
                        "model_tool_output_capabilities",
                        None,
                        (),
                        "v1 lacks configuration-specific tool-call/output capabilities; mandatory support needs verification",
                    )
                )
            for requirement in UNREPRESENTED:
                if requirement in prose:
                    checks.append(
                        _decision(
                            "unrepresented_hard_requirement",
                            None,
                            (),
                            f"Cannot evaluate {requirement!r} through the frozen contract; do not infer it from parameter count, prose or provider listing",
                        )
                    )
            result[candidate.id] = tuple(checks)
        return result

    def needing_verification(self, workflow: Workflow, catalog: CatalogSnapshot) -> tuple[str, ...]:
        return tuple(
            identifier
            for identifier, checks in self.assess(workflow, catalog).items()
            if all(c.value is not False for c in checks) and any(c.value is None for c in checks)
        )

    def contradicted(self, workflow: Workflow, catalog: CatalogSnapshot) -> tuple[str, ...]:
        return tuple(
            identifier
            for identifier, checks in self.assess(workflow, catalog).items()
            if any(c.value is False for c in checks)
        )

    def rank_for_verification(
        self, workflow: Workflow, catalog: CatalogSnapshot
    ) -> tuple[str, ...]:
        pending = set(self.needing_verification(workflow, catalog))
        return tuple(
            c.id
            for c in sorted(
                (c for c in catalog.configurations if c.id in pending),
                key=lambda c: self._price_key(c, catalog),
            )
        )

    def filter(self, workflow: Workflow, catalog: CatalogSnapshot) -> FilterResult:
        checks = self.assess(workflow, catalog)
        eligible = tuple(
            identifier
            for identifier, facts in checks.items()
            if all(f.value is True for f in facts)
        )
        excluded = {
            identifier: tuple(
                f"{'UNKNOWN' if f.value is None else 'CONTRADICTED'} {f.provenance.source}; sources={', '.join(f.provenance.evidence_ids) or 'none'}; {f.unknown_reason or 'hard requirement is contradicted'}"
                for f in facts
                if f.value is not True
            )
            for identifier, facts in checks.items()
            if identifier not in eligible
        }
        return FilterResult(eligible=eligible, excluded=excluded)

    @staticmethod
    def _price_key(
        candidate: CandidateConfiguration, catalog: CatalogSnapshot
    ) -> tuple[bool, float, str]:
        value = candidate.cost_per_1k_tokens.value
        known = (
            value is not None
            and math.isfinite(value)
            and value >= 0
            and _source_valid(candidate.cost_per_1k_tokens, catalog)
        )
        return (not known, value if known and value is not None else math.inf, candidate.id)

    def rank(
        self, workflow: Workflow, catalog: CatalogSnapshot, result: FilterResult
    ) -> tuple[str, ...]:
        # Recompute rather than trusting a caller-supplied eligible list from an old version.
        current = self.filter(workflow, catalog)
        if current != result:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Filter result is stale or inconsistent with this workflow/catalog",
                409,
            )
        return tuple(
            c.id
            for c in sorted(
                (c for c in catalog.configurations if c.id in current.eligible),
                key=lambda c: self._price_key(c, catalog),
            )
        )

    def compare(self, catalog: CatalogSnapshot, ranked: tuple[str, ...]) -> StackComparison:
        known = {c.id for c in catalog.configurations}
        if len(set(ranked)) != len(ranked) or not set(ranked) <= known:
            raise DomainError(
                ErrorCode.INVALID, "Comparison references unknown or duplicate configurations"
            )
        return StackComparison(
            configuration_ids=ranked[:1],
            rationale=f"{RULE_VERSION}: candidate-only view; no Workflow was supplied to this frozen port. Not an admissibility decision. First ranked configuration minimizes complexity; use compare_stacks for workload-aware bounded search.",
        )

    def _search(
        self, workflow: Workflow, catalog: CatalogSnapshot
    ) -> tuple[tuple[Assignment, ...], int, bool]:
        nodes = tuple(sorted(n.id for n in workflow.nodes if n.kind in ("llm", "bounded_agent")))
        if not nodes:
            return (), 1, True
        if len(nodes) > self.max_model_nodes:
            raise DomainError(
                ErrorCode.UNSUPPORTED,
                "Model-stage count exceeds the explicit portfolio search bound",
            )
        ranked = self.rank(workflow, catalog, self.filter(workflow, catalog))
        if not ranked:
            raise DomainError(
                ErrorCode.INVALID,
                "No admissible mapping: contradicted candidates excluded; unknown mandatory evidence remains needing verification",
            )
        considered = ranked[: self.max_candidates]
        rank_index = {identifier: rank for rank, identifier in enumerate(ranked)}
        best_score: tuple[int, int, tuple[str, ...]] | None = None
        best: tuple[str, ...] = ()
        searched = 0
        complete = len(considered) == len(ranked)
        exhausted = False
        for size in range(1, min(3, len(nodes), len(considered)) + 1):
            for portfolio in itertools.combinations(considered, size):
                for mapping in itertools.product(portfolio, repeat=len(nodes)):
                    if len(set(mapping)) != size:
                        continue  # unused configurations add no functional portfolio
                    if searched >= self.max_mappings:
                        exhausted = True
                        break
                    searched += 1
                    # Ordinal heuristic, not dollars, expected accuracy or savings.
                    score = (sum(rank_index[c] for c in mapping) + 2 * (size - 1), size, mapping)
                    if best_score is None or score < best_score:
                        best_score, best = score, mapping
                if exhausted:
                    break
            if exhausted:
                break
        assignments = tuple(
            Assignment(
                node_id=node,
                configuration_id=config,
                reason=f"{RULE_VERSION}: evidence-gated ordinal price rank plus 2-point penalty per extra configuration; provisional quality, not expected accuracy",
            )
            for node, config in zip(nodes, best, strict=True)
        )
        return assignments, searched, complete and not exhausted

    def compare_stacks(self, workflow: Workflow, catalog: CatalogSnapshot) -> StackComparison:
        assignments, searched, complete = self._search(workflow, catalog)
        configs = tuple(sorted({a.configuration_id for a in assignments}))
        artifacts = {c.artifact_id for c in catalog.configurations if c.id in configs}
        return StackComparison(
            configuration_ids=configs,
            rationale=(
                f"{RULE_VERSION}; distinct models={len(artifacts)}, configurations={len(configs)}; "
                f"searched mappings={searched}, complete={'yes' if complete else 'no'}; "
                f"bounds: candidates={self.max_candidates}, mappings={self.max_mappings}, model stages={self.max_model_nodes}, configurations per portfolio<=3. "
                "Rules: known evidence-linked unit price before unknown, then ordinal price rank per logical model stage + 2 points per extra configuration, then stable IDs. "
                "Logical stages are not actual call counts; no quality score is estimated. Optimal only within the enumerated mappings; no claim beyond searched space. "
                "v1 offers uniform workflow-level constraints, not stage-specific capabilities or benchmark/evaluation scope."
            ),
        )

    def recommend(
        self, workflow: Workflow, catalog: CatalogSnapshot, recommendation_id: str
    ) -> Recommendation:
        assignments, _, _ = self._search(workflow, catalog)
        filtered = self.filter(workflow, catalog)
        selected = {a.configuration_id for a in assignments}
        checks = self.assess(workflow, catalog)
        decisive = tuple(
            sorted(
                {
                    source
                    for identifier in selected
                    for fact in checks[identifier]
                    for source in fact.provenance.evidence_ids
                }
                | {
                    source
                    for c in catalog.configurations
                    if c.id in selected
                    for source in c.cost_per_1k_tokens.provenance.evidence_ids
                }
            )
        )
        summary = self.compare_stacks(workflow, catalog)
        return Recommendation(
            id=recommendation_id,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            catalog_id=catalog.id,
            assignments=assignments,
            alternatives=(),
            filter_result=filtered,
            evidence_ids=decisive,
            confidence="synthetic_only" if catalog.synthetic else "low",
            limitations=(
                summary.rationale,
                "Provisional: workload quality is not established. No unrelated benchmark scores were combined.",
                "Fallbacks omitted: v1 lacks typed fallback/retry behavior and stage-specific capability evidence; alternatives are not automatically safe fallback routes.",
                "Projected workflow spend unavailable: actual call/token/retry/tool/extra-component quantities are not present in v1. Unit prices are not savings or workflow costs.",
                "No-model stages: "
                + (
                    ", ".join(
                        n.id for n in workflow.nodes if n.kind not in ("llm", "bounded_agent")
                    )
                    or "none"
                ),
                "Missing contract fields block downloadable-artifact/legal suitability, context/output limits, hardware fit, privacy policy and scoped customer-evaluation claims.",
            ),
        )
