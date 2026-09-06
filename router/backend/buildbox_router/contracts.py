"""Canonical versioned contracts. Generate frontend types through OpenAPI."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class Workflow(Contract):
    id: Identifier
    version: int = Field(ge=1)
    title: str
    inputs: tuple[Identifier, ...]
    nodes: tuple[Node, ...] = Field(min_length=1, max_length=30)
    tools: tuple[WorkflowTool, ...] = ()
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


class CatalogSnapshot(Contract):
    id: Identifier
    artifacts: tuple[ModelArtifact, ...]
    configurations: tuple[CandidateConfiguration, ...]
    evidence: tuple[Evidence, ...]
    synthetic: bool

    @model_validator(mode="after")
    def references(self) -> "CatalogSnapshot":
        for rows in (self.artifacts, self.configurations, self.evidence):
            if len({r.id for r in rows}) != len(rows):
                raise ValueError("Duplicate catalog identifier")
        artifacts = {a.id for a in self.artifacts}
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
    status: Literal["queued", "running", "succeeded", "failed"]
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
