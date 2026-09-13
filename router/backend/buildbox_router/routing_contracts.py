"""Additive decision contracts; compose catalog/workflow/runtime, never permissions."""

from typing import Literal, cast

from pydantic import AwareDatetime, Field, model_validator

from .contracts import CatalogSnapshot, Identifier, Strategy, WorkloadProfile
from .execution_contracts import ExecutionContract, VersionRef

Objective = Literal[
    "quality", "latency", "cost", "throughput", "privacy", "reliability", "capability"
]


class RouterPolicy(ExecutionContract):
    id: Identifier = "balanced"
    version: int = Field(default=1, ge=1)
    weights: dict[Objective, float] = Field(
        default_factory=lambda: cast(
            dict[Objective, float],
            {
                "quality": 0.35,
                "latency": 0.2,
                "cost": 0.25,
                "privacy": 0.1,
                "reliability": 0.1,
            },
        )
    )
    unknown_penalty: float = Field(default=0.25, ge=0, le=1)
    estimated_discount: float = Field(default=0.25, ge=0, le=1)
    clear_margin: float = Field(default=0.1, ge=0, le=1)
    minimum_samples: int = Field(default=20, ge=1)
    circuit_failures: int = Field(default=3, ge=1, le=20)
    circuit_cooldown_seconds: int = Field(default=30, ge=1, le=3600)

    @model_validator(mode="after")
    def valid_weights(self) -> "RouterPolicy":
        if (
            not self.weights
            or any(v < 0 or v > 1 for v in self.weights.values())
            or sum(self.weights.values()) <= 0
        ):
            raise ValueError("Weights must be finite nonnegative values with positive total")
        return self


class WorkloadRequest(ExecutionContract):
    description: str = Field(min_length=1, max_length=8000, repr=False)
    overrides: WorkloadProfile | None = None


class PreviewRequest(WorkloadRequest):
    catalog_id: Identifier
    policy: RouterPolicy = Field(default_factory=RouterPolicy)
    # Explicitly reviewed completeness tokens; no model-supplied executable checks.
    required_terms: tuple[str, ...] = Field(default=(), max_length=20)


class CandidateUtility(ExecutionContract):
    configuration_id: Identifier
    eligible: bool
    rejected: tuple[str, ...] = ()
    metrics: dict[Objective, float | None] = Field(default_factory=dict)
    metric_basis: dict[Objective, str] = Field(default_factory=dict)
    normalized: dict[Objective, float] = Field(default_factory=dict)
    utility: float | None = None
    evidence_ids: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    pareto: bool = False


class StageDecision(ExecutionContract):
    node_id: Identifier
    depends_on: tuple[Identifier, ...]
    profile: WorkloadProfile
    selected: Identifier | None
    fallbacks: tuple[Identifier, ...] = ()
    candidates: tuple[CandidateUtility, ...]
    confidence: Literal["low", "medium", "high"]
    uncertainty: tuple[str, ...]
    explanation: str


class RoutingDecision(ExecutionContract):
    id: Identifier
    objective: str = Field(min_length=1, max_length=8000, repr=False)
    created_at: AwareDatetime
    catalog: CatalogSnapshot
    catalog_digest: str
    capability_schema: Literal["capabilities-1"] = "capabilities-1"
    profile: WorkloadProfile
    router_policy: RouterPolicy
    strategy: Strategy
    stages: tuple[StageDecision, ...]
    status: Literal["ready", "blocked"]
    blockers: tuple[str, ...] = ()
    projected_cost_micro_usd: float | None
    projected_latency_ms: float | None
    max_model_calls: int
    parallel_waves: tuple[tuple[str, ...], ...]
    strategy_reason: str
    required_terms: tuple[str, ...] = ()
    # False even for a complete deterministic preview; it is not an admission.
    activation_authority: Literal[False] = False


class WhatIfRequest(ExecutionContract):
    policy: RouterPolicy
    overrides: WorkloadProfile | None = None


class ShadowComparison(ExecutionContract):
    authoritative_decision: Identifier
    experimental_decision: Identifier
    disagreements: tuple[str, ...]
    metric_deltas: dict[str, float | None]
    executes_models: Literal[False] = False


class DraftFromDecision(ExecutionContract):
    decision_id: Identifier


class CatalogChange(ExecutionContract):
    configuration_id: str
    field: str
    before: str | None
    after: str | None


class CatalogDiffRequest(ExecutionContract):
    before: Identifier
    after: Identifier


class AdvancedScenario(ExecutionContract):
    id: Identifier
    title: str
    request: PreviewRequest
    decision_id: Identifier
    policy: VersionRef | None = None
    admission_id: Identifier | None = None
    input: str


class AdvancedStatus(ExecutionContract):
    catalog_ids: tuple[Identifier, ...]
    scenarios: tuple[AdvancedScenario, ...] = ()
    synthetic: bool


class PolicyEvaluationRequest(ExecutionContract):
    decisions: tuple[Identifier, ...] = Field(min_length=1, max_length=30)
    experimental: RouterPolicy


class PolicyEvaluationReport(ExecutionContract):
    id: Identifier
    comparisons: tuple[ShadowComparison, ...]
    case_count: int
    disagreement_rate: float
    kind: Literal["router_behavior_only"] = "router_behavior_only"
    model_quality_conclusion: Literal[False] = False


class RouterMetrics(ExecutionContract):
    coverage: str
    synthetic: bool
    decisions: int
    confidence_distribution: dict[str, int]
    configuration_distribution: dict[str, int]
    rejection_reasons: dict[str, int]
    attempts: int
    failure_rate: float | None
    fallback_rate: float | None
    average_latency_ms: float | None
    known_cost_micro_usd: int
    unknown_cost_attempts: int
    policy_disagreement_rate: float | None
