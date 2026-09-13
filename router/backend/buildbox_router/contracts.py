"""Canonical versioned contracts. Generate frontend types through OpenAPI."""

import math
from enum import StrEnum
from typing import Annotated, Literal, cast

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$")]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["1.0"] = "1.0"


class Provenance(Contract):
    kind: Literal["user_declared", "synthetic", "documented", "observed", "inference"]
    source: str = Field(min_length=1, max_length=500)
    evidence_ids: tuple[Identifier, ...] = ()


class Fact[T](Contract):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    value: T | None = None
    provenance: Provenance
    unknown_reason: str | None = None

    @model_validator(mode="after")
    def unknown_is_explicit(self) -> "Fact[T]":
        if self.value is None and not self.unknown_reason:
            raise ValueError("Unknown values require a reason")
        if self.value is not None and self.unknown_reason is not None:
            raise ValueError("Known values cannot carry an unknown reason")
        return self


class WorkflowTool(Contract):
    id: Identifier
    description: str
    declaration: Literal["user_declared"] = "user_declared"
    connected: Literal[False] = False


class ResearchTool(Contract):
    id: Identifier
    purpose: Literal["public_search", "public_extract"]


class ExecutionTool(Contract):
    id: Identifier
    connection_ref: Identifier
    enabled: Literal[False] = False


class Constraints(Contract):
    open_weight_required: Literal[True] = True
    max_cost_per_1k_tokens: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    required_region: str | None = None
    provenance: Provenance


class Intake(Contract):
    example_id: Identifier | None = None
    description: str = Field(min_length=1, max_length=8000)
    constraints: Constraints
    tools: tuple[WorkflowTool, ...] = ()


class Binding(Contract):
    source: Identifier
    output: Identifier
    from_input: bool = False


class Node(Contract):
    id: Identifier
    kind: Literal["llm", "tool", "code", "human_approval", "bounded_agent"]
    purpose: str
    depends_on: tuple[Identifier, ...] = ()
    inputs: dict[str, Binding] = Field(default_factory=dict)
    outputs: tuple[Identifier, ...] = ("result",)
    tool_id: Identifier | None = None
    allowed_tools: tuple[Identifier, ...] = ()
    max_iterations: int | None = Field(default=None, ge=1, le=10)
    max_model_calls: int | None = Field(default=None, ge=1, le=20)

    @model_validator(mode="after")
    def shape(self) -> "Node":
        if not self.outputs or len(set(self.outputs)) != len(self.outputs):
            raise ValueError("Node outputs must be nonempty and unique")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("Duplicate dependency")
        if (self.kind == "tool") != (self.tool_id is not None):
            raise ValueError("Only tool nodes must declare tool_id")
        if self.kind == "bounded_agent":
            if self.max_iterations is None or self.max_model_calls is None:
                raise ValueError("Agents require iteration and model-call bounds")
        elif (
            self.max_iterations is not None
            or self.max_model_calls is not None
            or self.allowed_tools
        ):
            raise ValueError("Loop bounds and allowed_tools are only for bounded agents")
        return self


class TargetRequirements(Contract):
    input_modality: Literal["text", "image"] = "text"
    deployment: Literal["any", "self_hosted", "api"] = "any"
    structured_output: bool = False
    tool_calling: bool = False


class Workflow(Contract):
    id: Identifier
    version: int = Field(ge=1)
    title: str
    inputs: tuple[Identifier, ...]
    nodes: tuple[Node, ...] = Field(min_length=1, max_length=30)
    tools: tuple[WorkflowTool, ...] = ()
    requirements: TargetRequirements = Field(default_factory=TargetRequirements)
    constraints: Constraints
    provenance: Provenance

    @model_validator(mode="after")
    def graph(self) -> "Workflow":
        ids = {n.id for n in self.nodes}
        tools = {t.id for t in self.tools}
        if len(ids) != len(self.nodes) or len(tools) != len(self.tools):
            raise ValueError("Node and tool IDs must be unique")
        if len(set(self.inputs)) != len(self.inputs):
            raise ValueError("Workflow input names must be unique")
        by_id = {n.id: n for n in self.nodes}
        for node in self.nodes:
            if not set(node.depends_on) <= ids or node.id in node.depends_on:
                raise ValueError("Missing or self dependency")
            if node.tool_id is not None and node.tool_id not in tools:
                raise ValueError("Undeclared workflow tool")
            if not set(node.allowed_tools) <= tools:
                raise ValueError("Undeclared agent tool")
            for binding in node.inputs.values():
                if binding.from_input:
                    if binding.source not in self.inputs or binding.output != "value":
                        raise ValueError("Invalid workflow input binding")
                elif (
                    binding.source not in node.depends_on
                    or binding.output not in by_id[binding.source].outputs
                ):
                    raise ValueError("Binding must reference an output of a direct dependency")
        visited: set[str] = set()
        visiting: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visiting:
                raise ValueError("Outer graph must be acyclic")
            if node_id in visited:
                return
            visiting.add(node_id)
            for parent in by_id[node_id].depends_on:
                visit(parent)
            visiting.remove(node_id)
            visited.add(node_id)

        for node_id in ids:
            visit(node_id)
        return self


class ModelArtifact(Contract):
    id: Identifier
    name: str
    revision: str
    open_weight: Fact[bool]
    license: Fact[str]
    provenance: Provenance


class CandidateConfiguration(Contract):
    id: Identifier
    artifact_id: Identifier
    provider: Fact[str]
    region: Fact[str]
    quantization: Fact[str]
    hardware: Fact[str]
    prompt_template_ref: Identifier
    harness_ref: Identifier
    reasoning_budget: Fact[int]
    cost_per_1k_tokens: Fact[float]
    latency_ms: Fact[float]
    provenance: Provenance


class Evidence(Contract):
    id: Identifier
    title: str
    claim: str
    source_url: str | None = None
    captured_at: str
    provenance: Provenance


class ConfigurationEligibility(Contract):
    configuration_id: Identifier
    artifact_id: Identifier
    # Contextual review of exact weights and license, not a hosted listing.
    weights_access: Fact[bool]
    license_policy: Fact[bool]
    input_modalities: Fact[tuple[str, ...]]
    supported_parameters: Fact[tuple[str, ...]]
    deployment: Fact[str]
    observed_at: str
    expires_at: str


# Normalized, additive intelligence facts. Identity stays on the existing artifact
# and serving configuration; these records never establish runtime authorization.
Capability = Literal[
    "text_input",
    "image_input",
    "audio_input",
    "video_input",
    "document_input",
    "text_output",
    "json_output",
    "schema_json",
    "code_output",
    "tools",
    "embeddings",
    "multimodal_output",
    "streaming",
    "context_tokens",
    "max_output_tokens",
    "quantization",
    "parameters_billion",
    "architecture",
    "family",
    "backends",
    "cold_start_ms",
    "latency_ms",
    "throughput_tokens_s",
    "input_usd_per_million",
    "output_usd_per_million",
    "request_usd",
    "gpu_count",
    "memory_gb",
    "self_hosted",
    "local",
    "privacy_class",
    "retention_days",
    "success_rate",
]
TaskFamily = Literal[
    "extraction",
    "summarization",
    "classification",
    "coding",
    "debugging",
    "mathematics",
    "science",
    "long_context",
    "tool_use",
    "structured_extraction",
    "research",
    "planning",
    "multilingual",
    "vision",
    "general",
]
Strategy = Literal["auto", "single", "multi_stage", "parallel", "cheap_first", "generate_verify"]


class CapabilityObservation(Contract):
    fact: Fact[JsonValue]
    basis: Literal["declared", "measured", "imported", "estimated", "synthetic", "unknown"]
    observed_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def valid_observation(self) -> "CapabilityObservation":
        if self.expires_at <= self.observed_at:
            raise ValueError("Capability expiry must follow observation")
        if (self.fact.value is None) != (self.basis == "unknown"):
            raise ValueError("Unknown capability must remain explicit")
        if self.basis == "synthetic" and self.fact.provenance.kind != "synthetic":
            raise ValueError("Synthetic fact must have synthetic provenance")
        if self.basis == "estimated" and self.fact.provenance.kind != "inference":
            raise ValueError("Estimates require inference provenance")
        allowed = {
            "declared": ("documented",),
            "measured": ("observed",),
            "imported": ("documented", "observed"),
        }
        if self.basis in allowed and self.fact.provenance.kind not in allowed[self.basis]:
            raise ValueError("Evidence basis contradicts fact provenance")
        return self


class DeploymentIntelligence(Contract):
    configuration_id: Identifier
    capability_schema: Literal["capabilities-1"] = "capabilities-1"
    facts: dict[Capability, CapabilityObservation]

    @model_validator(mode="after")
    def units_and_types(self) -> "DeploymentIntelligence":
        booleans = {
            "text_input",
            "image_input",
            "audio_input",
            "video_input",
            "document_input",
            "text_output",
            "json_output",
            "schema_json",
            "code_output",
            "tools",
            "embeddings",
            "multimodal_output",
            "streaming",
            "self_hosted",
            "local",
        }
        strings = {"quantization", "architecture", "family", "privacy_class"}
        for key, observation in self.facts.items():
            value = observation.fact.value
            if value is None:
                continue
            if key in booleans:
                valid = type(value) is bool
            elif key in strings:
                valid = isinstance(value, str)
            elif key == "backends":
                valid = isinstance(value, list) and all(isinstance(v, str) for v in value)
            else:
                valid = (
                    type(value) in (int, float)
                    and math.isfinite(cast(float, value))
                    and cast(float, value) >= 0
                )
                if key == "success_rate":
                    valid = valid and cast(float, value) <= 1
            if not valid:
                raise ValueError(f"Invalid normalized capability value for {key}")
        return self


class PerformanceEvidence(Contract):
    id: Identifier
    configuration_id: Identifier
    task: TaskFamily
    benchmark: str = Field(min_length=1, max_length=200)
    benchmark_version: str
    split: str
    harness: str
    settings: str
    raw_metric: float = Field(allow_inf_nan=False)
    unit: str
    # Only an explicitly reviewed, task-scoped [0,1] conversion is rankable.
    normalized_score: float = Field(ge=0, le=1, allow_inf_nan=False)
    normalization: str = Field(min_length=1)
    scale_min: float = Field(default=0, allow_inf_nan=False)
    scale_max: float = Field(default=1, allow_inf_nan=False)
    higher_is_better: bool = True
    sample_size: int | None = Field(default=None, ge=1)
    measured_at: AwareDatetime | None = None
    retrieved_at: AwareDatetime
    expires_at: AwareDatetime
    source_url: str | None = None
    source_locator: str = Field(min_length=1)
    provenance: Provenance
    origin: Literal["internal_evaluation", "curated_import", "manual_review", "synthetic"]
    reviewed: bool = False
    limitations: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def dates(self) -> "PerformanceEvidence":
        if (
            self.scale_max <= self.scale_min
            or not self.scale_min <= self.raw_metric <= self.scale_max
        ):
            raise ValueError("Benchmark normalization needs a valid explicit scale")
        expected = (self.raw_metric - self.scale_min) / (self.scale_max - self.scale_min)
        if not self.higher_is_better:
            expected = 1 - expected
        if not math.isclose(self.normalized_score, expected, abs_tol=1e-9):
            raise ValueError("Normalized benchmark score contradicts raw metric/scale")
        if self.expires_at <= self.retrieved_at or (
            self.measured_at and self.measured_at > self.retrieved_at
        ):
            raise ValueError("Invalid performance dates; retrieval is not measurement")
        if (self.origin == "synthetic") != (self.provenance.kind == "synthetic"):
            raise ValueError("Synthetic performance must remain labeled")
        return self


class WorkloadProfile(Contract):
    analyzer_version: Literal["workload-rules-1"] = "workload-rules-1"
    task: TaskFamily = "general"
    complexity: Literal["simple", "moderate", "complex", "unknown"] = "unknown"
    required: tuple[Capability, ...] = ("text_input", "text_output")
    optional: tuple[Capability, ...] = ()
    input_tokens: int | None = Field(default=None, ge=1, le=131072)
    output_tokens: int | None = Field(default=None, ge=1, le=16384)
    latency_sensitivity: Literal["low", "medium", "high", "unknown"] = "unknown"
    quality_sensitivity: Literal["low", "medium", "high", "unknown"] = "unknown"
    budget_sensitivity: Literal["low", "medium", "high", "unknown"] = "unknown"
    local_only: bool = False
    self_hosted_only: bool = False
    approved_providers: tuple[str, ...] = ()
    no_retention: bool = False
    no_external_tools: bool = True
    data_class: Literal["synthetic", "public", "tenant_private", "restricted"] = "tenant_private"
    tools: tuple[Identifier, ...] = ()
    structured_output: Literal["text", "json", "schema_json"] = "text"
    determinism: Literal["required", "preferred", "unspecified"] = "unspecified"
    expected_stages: int | None = Field(default=None, ge=1, le=8)
    decomposition: bool | None = None
    verification: bool | None = None
    parallel: bool | None = None
    strategy: Strategy = "auto"
    max_cost_micro_usd: int | None = Field(default=None, ge=0, le=1000000)
    preferred_cost_micro_usd: int | None = Field(default=None, ge=0, le=1000000)
    max_latency_ms: int | None = Field(default=None, ge=100, le=120000)
    min_quality: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    max_model_calls: int = Field(default=6, ge=1, le=20)
    max_tool_calls: int = Field(default=0, ge=0, le=20)
    max_attempts: int = Field(default=2, ge=1, le=3)
    # Evidence is rule identifiers and field names, never retained private input.
    evidence: dict[str, str] = Field(default_factory=dict)
    explicit_fields: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()


class CatalogSnapshot(Contract):
    id: Identifier
    artifacts: tuple[ModelArtifact, ...]
    configurations: tuple[CandidateConfiguration, ...]
    evidence: tuple[Evidence, ...]
    synthetic: bool
    eligibility: tuple[ConfigurationEligibility, ...] = ()
    intelligence: tuple[DeploymentIntelligence, ...] = ()
    performance: tuple[PerformanceEvidence, ...] = ()

    @model_validator(mode="after")
    def references(self) -> "CatalogSnapshot":
        for rows in (self.artifacts, self.configurations, self.evidence):
            if len({r.id for r in rows}) != len(rows):
                raise ValueError("Duplicate catalog identifier")
        artifacts = {a.id for a in self.artifacts}
        configs = {c.id: c for c in self.configurations}
        if len({x.configuration_id for x in self.intelligence}) != len(self.intelligence):
            raise ValueError("Duplicate deployment intelligence")
        if len({x.id for x in self.performance}) != len(self.performance):
            raise ValueError("Duplicate performance evidence")
        for intelligence in self.intelligence:
            if intelligence.configuration_id not in configs:
                raise ValueError("Intelligence must reference exact deployment configuration")
        for performance in self.performance:
            if performance.configuration_id not in configs:
                raise ValueError("Performance must reference exact deployment configuration")
        if not self.synthetic and any(p.origin == "synthetic" for p in self.performance):
            raise ValueError("Synthetic performance cannot enter a public/live catalog")
        if len({e.configuration_id for e in self.eligibility}) != len(self.eligibility):
            raise ValueError("Duplicate configuration eligibility")
        for item in self.eligibility:
            if (
                item.configuration_id not in configs
                or configs[item.configuration_id].artifact_id != item.artifact_id
            ):
                raise ValueError("Eligibility identity differs from configuration/artifact")
        evidence = {e.id for e in self.evidence}
        for config in self.configurations:
            if config.artifact_id not in artifacts:
                raise ValueError("Unknown model artifact")
        provenances = [a.provenance for a in self.artifacts] + [
            c.provenance for c in self.configurations
        ]
        for provenance in provenances:
            if not set(provenance.evidence_ids) <= evidence:
                raise ValueError("Unresolved catalog evidence")
        return self


class Clarification(Contract):
    field: str
    question: str
    material: bool = True


class Interpretation(Contract):
    status: Literal["ready", "needs_clarification", "unsupported"]
    workflow: Workflow | None = None
    questions: tuple[Clarification, ...] = ()


class FilterResult(Contract):
    eligible: tuple[Identifier, ...]
    excluded: dict[str, tuple[str, ...]]


class Assignment(Contract):
    node_id: Identifier
    configuration_id: Identifier
    reason: str


class Recommendation(Contract):
    id: Identifier
    workflow_id: Identifier
    workflow_version: int
    catalog_id: Identifier
    assignments: tuple[Assignment, ...]
    alternatives: tuple[Identifier, ...]
    filter_result: FilterResult
    evidence_ids: tuple[Identifier, ...]
    confidence: Literal["synthetic_only", "low", "medium", "high"]
    limitations: tuple[str, ...]


class StackComparison(Contract):
    configuration_ids: tuple[Identifier, ...]
    rationale: str
    quality_verified: bool = False


class EvaluationRun(Contract):
    id: Identifier
    recommendation_id: Identifier
    status: Literal["not_run", "completed", "failed"]
    holdout_ref: Identifier
    metric: Fact[float]
    synthetic: bool
    production_write: Literal[False] = False


class DraftPolicy(Contract):
    id: Identifier
    workflow_id: Identifier
    workflow_version: int
    recommendation_id: Identifier
    assignments: tuple[Assignment, ...]
    status: Literal["draft"] = "draft"
    active: Literal[False] = False
    production_write: Literal[False] = False
    requires_human_approval: Literal[True] = True
    execution_tools: tuple[ExecutionTool, ...] = ()
    synthetic: bool


class ErrorCode(StrEnum):
    INVALID = "invalid_request"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNSUPPORTED = "unsupported_mode"
    INTERNAL = "internal_error"


class ErrorResponse(Contract):
    code: ErrorCode
    message: str
    retryable: bool = False


class Job(Contract):
    id: Identifier
    workflow_id: Identifier
    workflow_version: int
    status: Literal["queued", "running", "succeeded", "failed", "cancelled", "uncertain"]
    operation: Literal["recommendation", "planning"] = "recommendation"
    served_configuration: dict[str, str | int | float] = Field(default_factory=dict)
    phase: str = "queued"
    progress: tuple[str, ...] = ()
    reserved_usd: float = Field(default=0, ge=0, allow_inf_nan=False)
    accounted_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    accounting: Literal["not_started", "reserved", "known", "uncertain"] = "not_started"
    attempts: int = 0
    recommendation_id: Identifier | None = None
    error: ErrorResponse | None = None
    created_at: float
    updated_at: float


class Example(Contract):
    id: Identifier
    title: str
    intake: Intake
    synthetic: Literal[True] = True


class Submission(Contract):
    intake_id: Identifier
    interpretation: Interpretation
    job: Job | None = None
