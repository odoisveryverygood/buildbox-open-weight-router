"""Canonical sandbox v2 contracts. These describe authority; they never grant it.

Planning Workflow/CatalogSnapshot remain canonical, unchanged and non-executable.
The OpenAI-compatible wire subset intentionally has no Buildbox schema_version.
"""

import hashlib
import json
import re
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from .contracts import CandidateConfiguration, Fact, Identifier, TargetRequirements, Workflow
from .evidence_contracts import EndpointRecord
from .json_contracts import JsonSchema


class Wire(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        allow_inf_nan=False,
        populate_by_name=True,
        serialize_by_alias=True,
    )


class ExecutionContract(Wire):
    execution_schema: Literal["2.0"] = "2.0"


def digest(value: BaseModel) -> str:
    def legacy_defaults(item: object) -> object:
        # Additive defaults must not invalidate an already signed 2.0 policy.
        defaults = {
            "fallback_configuration_ids": (),
            "route_requirements": None,
            "variant": None,
            "response_format": None,
            "max_attempts": 1,
            "requirements": TargetRequirements().model_dump(mode="json"),
        }
        if isinstance(item, dict):
            return {
                k: legacy_defaults(v)
                for k, v in item.items()
                if k not in defaults
                or (v != defaults[k] and not (k == "fallback_configuration_ids" and v == []))
            }
        if isinstance(item, list):
            return [legacy_defaults(v) for v in item]
        return item

    return hashlib.sha256(
        json.dumps(
            legacy_defaults(value.model_dump(mode="json")), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


class VersionRef(ExecutionContract):
    id: Identifier
    version: int = Field(ge=1)


ValueType = Literal["text", "json", "boolean", "number"]
Operation = Literal[
    "text.trim.v1",
    "text.lowercase.v1",
    "text.uppercase.v1",
    "text.sort_lines.v1",
    "text.deduplicate_lines.v1",
]
Scope = Literal["models:read", "chat:complete", "workflow:run", "runs:read", "runs:cancel"]


class ExecutionBudget(ExecutionContract):
    # Integer micro-USD; no blended per-token prices or floating point reservations.
    max_cost_micro_usd: int = Field(ge=0, le=1_000_000, strict=True)
    max_model_calls: int = Field(ge=0, le=20, strict=True)
    max_tool_calls: int = Field(ge=0, le=20, strict=True)
    max_input_tokens: int = Field(ge=1, le=131072, strict=True)
    max_output_tokens: int = Field(ge=1, le=16384, strict=True)
    timeout_ms: int = Field(ge=100, le=120000, strict=True)
    max_retries: Literal[0] = 0
    max_attempts: int = Field(default=1, ge=1, le=3, strict=True)


class StopConditions(ExecutionContract):
    on_error: Literal["stop"] = "stop"
    on_budget_exhausted: Literal["stop"] = "stop"
    on_cancel: Literal["stop_before_next_dispatch"] = "stop_before_next_dispatch"
    on_human_approval: Literal["pause"] = "pause"


class PromptRevision(ExecutionContract):
    id: Identifier
    version: int = Field(ge=1)
    template: str = Field(min_length=1, max_length=16000, repr=False)
    variables: dict[Identifier, ValueType]
    parent: VersionRef | None = None
    engine: Literal["literal_placeholders_v1"] = "literal_placeholders_v1"

    @model_validator(mode="after")
    def placeholders(self) -> "PromptRevision":
        if set(re.findall(r"\{\{([A-Za-z0-9_-]+)\}\}", self.template)) != set(self.variables):
            raise ValueError("Prompt placeholders and typed variables must match exactly")
        if self.parent and (self.parent.id != self.id or self.parent.version != self.version - 1):
            raise ValueError("Prompt parent must be the preceding exact revision")
        if (self.version > 1) != (self.parent is not None):
            raise ValueError("Prompt revision requires its parent")
        return self


class RouteRequirements(ExecutionContract):
    allowed_endpoint_ids: tuple[Identifier, ...] = ()
    required_parameters: tuple[str, ...] = ()
    local_only: bool = False
    required_region: str | None = None


class PolicyVariant(ExecutionContract):
    mode: Literal["quality", "balanced", "cost_conscious"]
    rule_version: Literal["sandbox-heuristic-1"] = "sandbox-heuristic-1"
    rationale: tuple[str, ...]
    quality_validated: Literal[False] = False


class VariantRequest(ExecutionContract):
    id: Identifier
    mode: Literal["quality", "balanced", "cost_conscious"]


class PolicyEditRequest(ExecutionContract):
    instruction: str = Field(default="", max_length=2000)
    pins: dict[Identifier, Identifier] = Field(default_factory=dict)
    exclude_configuration_ids: tuple[Identifier, ...] = Field(default=(), max_length=30)
    prompt_templates: dict[Identifier, str] = Field(default_factory=dict)
    output_schemas: dict[Identifier, JsonSchema] = Field(default_factory=dict)
    cheaper_stage_ids: tuple[Identifier, ...] = ()


class PolicyHistory(ExecutionContract):
    versions: tuple[VersionRef, ...]


class ExecutableStage(ExecutionContract):
    node_id: Identifier
    input_types: dict[Identifier, ValueType]
    output_types: dict[Identifier, ValueType]
    prompt: VersionRef | None = None
    configuration_id: Identifier | None = None
    fallback_configuration_ids: tuple[Identifier, ...] = Field(default=(), max_length=2)
    route_requirements: RouteRequirements | None = None
    response_format: "ResponseFormat | None" = None
    operation: Operation | None = None
    allowed_tool_ids: tuple[Identifier, ...] = ()
    budget: ExecutionBudget
    stop: StopConditions = Field(default_factory=StopConditions)


class ExecutablePolicy(ExecutionContract):
    id: Identifier
    version: int = Field(ge=1)
    plan: VersionRef
    workflow: Workflow
    catalog_id: Identifier
    input_types: dict[Identifier, ValueType]
    stages: tuple[ExecutableStage, ...] = Field(min_length=1, max_length=30)
    prompts: tuple[PromptRevision, ...] = Field(default=(), max_length=30)
    budget: ExecutionBudget
    quality: Literal["untested_provisional", "measured_not_production_approved"] = (
        "untested_provisional"
    )
    environment: Literal["sandbox"] = "sandbox"
    production_approved: Literal[False] = False
    variant: PolicyVariant | None = None

    @model_validator(mode="after")
    def executable_bindings(self) -> "ExecutablePolicy":
        if (self.workflow.id, self.workflow.version) != (self.plan.id, self.plan.version):
            raise ValueError("Plan/workflow version mismatch")
        nodes = {n.id: n for n in self.workflow.nodes}
        stages = {s.node_id: s for s in self.stages}
        prompts = {(p.id, p.version): p for p in self.prompts}
        if len(stages) != len(self.stages) or set(stages) != set(nodes):
            raise ValueError("Exactly one executable stage required per workflow node")
        if len(prompts) != len(self.prompts) or set(self.input_types) != set(self.workflow.inputs):
            raise ValueError("Duplicate prompts or missing typed workflow inputs")
        used_prompts = set()
        for name, stage in stages.items():
            node = nodes[name]
            if (
                len(set(stage.fallback_configuration_ids)) != len(stage.fallback_configuration_ids)
                or stage.configuration_id in stage.fallback_configuration_ids
            ):
                raise ValueError("Fallback pins must be distinct")
            if stage.fallback_configuration_ids and (
                node.kind != "llm"
                or len(stage.fallback_configuration_ids) + 1 > stage.budget.max_attempts
            ):
                raise ValueError("Fallbacks require explicit bounded model attempts")
            if stage.response_format is not None and node.kind != "llm":
                raise ValueError("Only LLM stages have response formats")
            if node.kind == "bounded_agent":
                raise ValueError("Bounded agents remain planning-only in sandbox v2.0")
            if (
                not node.inputs
                or set(stage.input_types) != set(node.inputs)
                or set(stage.output_types) != set(node.outputs)
            ):
                raise ValueError("Executable nodes need complete typed input/output bindings")
            for field, binding in node.inputs.items():
                source_type = (
                    self.input_types[binding.source]
                    if binding.from_input
                    else stages[binding.source].output_types[binding.output]
                )
                if stage.input_types[field] != source_type:
                    raise ValueError("Incompatible stage binding types")
            if (node.kind == "llm") != (
                stage.prompt is not None and stage.configuration_id is not None
            ):
                raise ValueError("Only LLM stages have prompt and configuration bindings")
            if node.kind != "llm" and (
                stage.prompt is not None or stage.configuration_id is not None
            ):
                raise ValueError("Non-model stage cannot carry partial model bindings")
            if node.kind == "llm":
                assert stage.prompt is not None
                key = (stage.prompt.id, stage.prompt.version)
                if key not in prompts or prompts[key].variables != stage.input_types:
                    raise ValueError("Prompt revision/variables do not match stage")
                used_prompts.add(key)
                if (
                    stage.budget.max_model_calls != stage.budget.max_attempts
                    or stage.budget.max_tool_calls != 0
                ):
                    raise ValueError(
                        "LLM stages budget every possible attempt and never business tools"
                    )
            elif stage.budget.max_model_calls != 0:
                raise ValueError("Non-model stage cannot budget model calls")
            if (node.kind == "code") != (stage.operation is not None):
                raise ValueError("Code must name an approved deterministic operation")
            if node.kind == "code" and (
                stage.input_types != {"text": "text"} or stage.output_types != {"result": "text"}
            ):
                raise ValueError("v1 text operations use text -> result:text only")
            expected_tools = (node.tool_id,) if node.kind == "tool" else ()
            if stage.allowed_tool_ids != expected_tools or stage.budget.max_tool_calls != (
                1 if expected_tools else 0
            ):
                raise ValueError("Tool allowlist and per-stage call count mismatch")
            for limit in (
                "max_cost_micro_usd",
                "max_input_tokens",
                "max_output_tokens",
                "timeout_ms",
            ):
                if getattr(stage.budget, limit) > getattr(self.budget, limit):
                    raise ValueError("Stage bound exceeds workflow bound")
        for limit in ("max_cost_micro_usd", "max_model_calls", "max_tool_calls"):
            if sum(getattr(s.budget, limit) for s in self.stages) > getattr(self.budget, limit):
                raise ValueError("Stage reservations exceed workflow budget")
        if used_prompts != set(prompts):
            raise ValueError("Unbound prompt revisions are not part of an executable policy")
        return self


class SandboxAdmission(ExecutionContract):
    """Operator-only record; never accepted from a studio/public HTTP payload."""

    id: Identifier
    tenant_id: Identifier
    policy: VersionRef
    policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    configuration_ids: tuple[Identifier, ...]
    credential_reference_ids: tuple[Identifier, ...] = ()
    allowed_tool_ids: tuple[Identifier, ...] = ()
    authorization_reference: Identifier
    budget_reference: Identifier
    privacy: Fact[bool]
    license_policy: Fact[bool]
    weights_access: Fact[bool]
    capabilities: Fact[bool]
    spending: Fact[bool]
    expires_at: AwareDatetime


class PolicyTransition(ExecutionContract):
    policy: VersionRef
    sequence: int = Field(ge=1)
    status: Literal["draft", "sandbox_enabled", "disabled"]
    admission_id: Identifier | None = None
    actor_id: Identifier
    occurred_at: AwareDatetime
    production_approved: Literal[False] = False


class TransitionRequest(ExecutionContract):
    expected_sequence: int = Field(ge=1)
    status: Literal["sandbox_enabled", "disabled"]
    admission_id: Identifier | None = None


class PolicyView(ExecutionContract):
    policy: ExecutablePolicy
    transition: PolicyTransition


class RouteAlias(ExecutionContract):
    id: Identifier
    policy: VersionRef
    node_id: Identifier
    configuration_id: Identifier
    created_at: AwareDatetime
    environment: Literal["sandbox"] = "sandbox"


class ApplicationKeyMetadata(ExecutionContract):
    id: Identifier
    tenant_id: Identifier
    prefix: str = Field(pattern=r"^bbx_[a-zA-Z0-9]{8}$")
    scopes: tuple[Scope, ...] = Field(min_length=1)
    alias_ids: tuple[Identifier, ...] = ()
    workflow_policies: tuple[VersionRef, ...] = ()
    created_at: AwareDatetime
    expires_at: AwareDatetime
    revoked_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def dates(self) -> "ApplicationKeyMetadata":
        if self.expires_at <= self.created_at or (
            self.revoked_at and self.revoked_at < self.created_at
        ):
            raise ValueError("Invalid key lifetime")
        if len(set(self.scopes)) != len(self.scopes) or len(set(self.alias_ids)) != len(
            self.alias_ids
        ):
            raise ValueError("Duplicate key scope or alias")
        return self


class ProviderCredentialReference(ExecutionContract):
    id: Identifier
    tenant_id: Identifier
    adapter_id: Literal["openrouter", "local_ollama", "openai_compatible"]
    secret_reference: Identifier | None = Field(default=None, repr=False)
    approval_reference: Identifier
    expires_at: AwareDatetime
    # No key value, environment value, session token, or arbitrary URL accepted.


class RuntimeGrant(ExecutionContract):
    """Operator approval for TARGET sandbox calls; planning roles cannot substitute."""

    id: Identifier
    tenant_id: Identifier
    purpose: Literal["target_sandbox"] = "target_sandbox"
    configuration_ids: tuple[Identifier, ...]
    credential_reference_ids: tuple[Identifier, ...]
    allowed_data_classes: tuple[Literal["synthetic", "tenant_private"], ...]
    budget_reference: Identifier
    permission_reference: Identifier
    expires_at: AwareDatetime


class LocalDeployment(ExecutionContract):
    adapter_id: Literal["local_ollama"] = "local_ollama"
    model_tag: str = Field(pattern=r"^[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+$")
    weights_digest: Fact[str]
    supported_parameters: Fact[tuple[str, ...]]
    context_tokens: Fact[int]
    max_output_tokens: Fact[int]
    privacy: Fact[str]


class TargetConfiguration(ExecutionContract):
    """Canonical catalog extension: advertised facts != observations from our runs."""

    configuration: CandidateConfiguration
    catalog_id: Identifier
    endpoint: EndpointRecord | None = None
    local: LocalDeployment | None = None
    observed_run_ids: tuple[Identifier, ...] = ()
    limitations: tuple[str, ...] = Field(min_length=1)
    approved_endpoint_id: Identifier | None = None
    expires_at: AwareDatetime | None = None
    token_envelope_approved: Fact[bool] | None = None

    @model_validator(mode="after")
    def deployment(self) -> "TargetConfiguration":
        if (self.endpoint is None) == (self.local is None):
            raise ValueError("Exactly one explicit deployment identity required")
        if self.endpoint and self.endpoint.artifact_id != self.configuration.artifact_id:
            raise ValueError("Endpoint/artifact identity mismatch")
        return self


class FunctionDefinition(Wire):
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    description: str | None = Field(default=None, max_length=1000)
    parameters: JsonSchema
    strict: Literal[True] = True


class ToolDefinition(Wire):
    type: Literal["function"] = "function"
    function: FunctionDefinition


class FunctionChoice(Wire):
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")


class NamedToolChoice(Wire):
    type: Literal["function"] = "function"
    function: FunctionChoice


class FunctionCall(Wire):
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    arguments: str = Field(max_length=65536, repr=False)


class ToolCall(Wire):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,120}$")
    type: Literal["function"] = "function"
    function: FunctionCall


class JsonSchemaFormat(Wire):
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    strict: Literal[True] = True
    schema_: JsonSchema = Field(alias="schema")


class ResponseFormat(Wire):
    type: Literal["text", "json_object", "json_schema"]
    json_schema: JsonSchemaFormat | None = None

    @model_validator(mode="after")
    def schema_required(self) -> "ResponseFormat":
        if (self.type == "json_schema") != (self.json_schema is not None):
            raise ValueError("JSON schema format requires exactly its schema")
        return self


class ChatMessage(Wire):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = Field(default=None, max_length=16000, repr=False)
    tool_calls: tuple[ToolCall, ...] | None = Field(default=None, min_length=1, max_length=8)
    tool_call_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,120}$")

    @model_validator(mode="after")
    def role_fields(self) -> "ChatMessage":
        if self.role != "assistant" and self.tool_calls is not None:
            raise ValueError("Only assistant messages contain tool calls")
        if (self.role == "tool") != (self.tool_call_id is not None):
            raise ValueError("Tool results require call ID")
        if self.content is None and not self.tool_calls:
            raise ValueError("Message needs text or tool calls")
        return self


class ChatCompletionRequest(Wire):
    model: Identifier  # tenant-scoped alias, NOT arbitrary provider/model name
    messages: tuple[ChatMessage, ...] = Field(min_length=1, max_length=32)
    max_tokens: int = Field(ge=1, le=16384, strict=True)
    temperature: float | None = Field(default=None, ge=0, le=2, strict=True, allow_inf_nan=False)
    stream: bool = Field(default=False, strict=True)
    tools: tuple[ToolDefinition, ...] | None = Field(default=None, min_length=1, max_length=8)
    tool_choice: Literal["auto", "none", "required"] | NamedToolChoice | None = None
    response_format: ResponseFormat | None = None

    @model_validator(mode="after")
    def combinations(self) -> "ChatCompletionRequest":
        names = [t.function.name for t in self.tools or ()]
        if len(set(names)) != len(names) or (self.tool_choice is not None and not names):
            raise ValueError("Unique declared tools required by tool_choice")
        if (
            isinstance(self.tool_choice, NamedToolChoice)
            and self.tool_choice.function.name not in names
        ):
            raise ValueError("Named tool is undeclared")
        if (
            self.response_format
            and self.response_format.type != "text"
            and (self.stream or self.tools)
        ):
            raise ValueError("Strict JSON delivery supports nonstream without tools only")
        pending: set[str] = set()
        seen: set[str] = set()
        for message in self.messages:
            if pending and message.role != "tool":
                raise ValueError("Supply every pending tool result before continuing")
            if message.role == "tool":
                if message.tool_call_id not in pending:
                    raise ValueError("Tool result does not match a pending call")
                pending.remove(message.tool_call_id)
            for call in message.tool_calls or ():
                if call.id in seen or call.function.name not in names:
                    raise ValueError("Tool history has duplicate ID or undeclared tool")
                pending.add(call.id)
                seen.add(call.id)
        if pending:
            raise ValueError("Cannot submit an unresolved tool invocation")
        return self


class CompletionUsage(Wire):
    prompt_tokens: int = Field(ge=0, strict=True)
    completion_tokens: int = Field(ge=0, strict=True)
    total_tokens: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def total(self) -> "CompletionUsage":
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("Inconsistent token usage")
        return self


class CompletionMessage(Wire):
    role: Literal["assistant"] = "assistant"
    content: str | None = Field(default=None, max_length=1_048_576, repr=False)
    tool_calls: tuple[ToolCall, ...] | None = Field(default=None, min_length=1, max_length=8)


class CompletionChoice(Wire):
    index: Literal[0] = 0
    message: CompletionMessage
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls"]


class ChatCompletion(Wire):
    id: Identifier
    object: Literal["chat.completion"] = "chat.completion"
    created: int = Field(ge=0)
    model: Identifier  # immutable requested alias; actual provider goes in decision trace
    choices: tuple[CompletionChoice, ...] = Field(min_length=1, max_length=1)
    usage: CompletionUsage | None = None  # unknown is not zero


class FunctionDelta(Wire):
    name: str | None = None
    arguments: str | None = Field(default=None, max_length=65536, repr=False)


class ToolCallDelta(Wire):
    index: int = Field(ge=0, le=7)
    id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,120}$")
    type: Literal["function"] | None = None
    function: FunctionDelta | None = None


class CompletionDelta(Wire):
    role: Literal["assistant"] | None = None
    content: str | None = Field(default=None, max_length=65536, repr=False)
    tool_calls: tuple[ToolCallDelta, ...] | None = Field(default=None, min_length=1, max_length=8)


class ChunkChoice(Wire):
    index: Literal[0] = 0
    delta: CompletionDelta
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls"] | None = None


class ChatCompletionChunk(Wire):
    id: Identifier
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int = Field(ge=0)
    model: Identifier
    choices: tuple[ChunkChoice, ...] = Field(max_length=1)
    usage: CompletionUsage | None = None


class ModelListing(Wire):
    id: Identifier
    object: Literal["model"] = "model"
    created: int = Field(ge=0)
    owned_by: Literal["buildbox-sandbox"] = "buildbox-sandbox"


class ModelList(Wire):
    object: Literal["list"] = "list"
    data: tuple[ModelListing, ...]


class GatewayErrorDetail(Wire):
    message: str
    type: Literal[
        "invalid_request_error",
        "authentication_error",
        "permission_error",
        "rate_limit_error",
        "server_error",
    ]
    param: str | None = None
    code: Literal[
        "unsupported_parameter",
        "invalid_request",
        "unauthorized",
        "sandbox_disabled",
        "admission_denied",
        "budget_exhausted",
        "runtime_unavailable",
        "cancelled",
        "timeout",
        "accounting_uncertain",
        "partial_failure",
        "upstream_error",
    ]


class GatewayError(Wire):
    error: GatewayErrorDetail


class UsageReconciliation(ExecutionContract):
    reservation_id: Identifier
    reserved_micro_usd: int = Field(ge=0, strict=True)
    actual_micro_usd: int | None = Field(default=None, ge=0, strict=True)
    state: Literal["reserved", "reconciled", "uncertain"]
    tokens: CompletionUsage | None = None
    observed_at: AwareDatetime

    @model_validator(mode="after")
    def reconciled(self) -> "UsageReconciliation":
        if (self.state == "reconciled") != (self.actual_micro_usd is not None):
            raise ValueError("Only reconciled usage has known actual cost")
        return self


class DecisionTrace(ExecutionContract):
    request_id: Identifier
    tenant_id: Identifier
    policy: VersionRef
    transition_sequence: int = Field(ge=1)
    alias_id: Identifier | None = None
    node_id: Identifier
    configuration_id: Identifier | None = None
    catalog_id: Identifier
    prompt: VersionRef | None = None
    admission_id: Identifier
    evidence_ids: tuple[Identifier, ...]
    requested_endpoint: str | None = Field(default=None, max_length=200)
    served_model: Fact[str]
    served_endpoint: Fact[str]
    quality: Literal["untested_provisional", "measured_not_production_approved"]
    # No input text, raw provider payload, credentials, or chain-of-thought.


class RunAttempt(ExecutionContract):
    id: Identifier
    run_id: Identifier
    node_id: Identifier
    attempt: int = Field(default=1, ge=1, le=3)
    status: Literal["reserved", "dispatched", "succeeded", "failed", "cancelled", "uncertain"]
    trace: DecisionTrace
    usage: UsageReconciliation
    output_reference: Identifier | None = None
    error: GatewayError | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    gateway_overhead_ms: int | None = Field(default=None, ge=0)
    upstream_ms: int | None = Field(default=None, ge=0)
    time_to_first_content_ms: int | None = Field(default=None, ge=0)
    latency_definition: Literal["reservation_to_finalization_wall_clock"] = (
        "reservation_to_finalization_wall_clock"
    )


class StreamObservation(ExecutionContract):
    type: Literal["observation"] = "observation"
    usage: CompletionUsage | None = None
    actual_micro_usd: int | None = Field(default=None, ge=0, strict=True)
    trace: DecisionTrace


class ApprovedEndpoint(ExecutionContract):
    id: Identifier
    tenant_id: Identifier
    url: str = Field(max_length=300, repr=False)
    network: Literal["public_https", "loopback"]
    adapter_id: Literal["openrouter", "openai_compatible"]
    credential_reference_id: Identifier
    expires_at: AwareDatetime
    authorization_reference: Identifier


class KeyIssueRequest(ExecutionContract):
    expires_at: AwareDatetime
    scopes: tuple[Scope, ...] = Field(min_length=1)
    alias_ids: tuple[Identifier, ...] = ()
    workflow_policies: tuple[VersionRef, ...] = ()
    max_cost_micro_usd: int = Field(ge=0, le=1000000, strict=True)


class IssuedKey(ExecutionContract):
    metadata: ApplicationKeyMetadata
    secret: str = Field(repr=False)


class RuntimeStatus(ExecutionContract):
    installed: bool
    mode: Literal["disabled", "approved", "synthetic_test"]
    live_verified: Literal[False] = False
    target_count: int | None = Field(default=None, ge=0)
    detail: str
    available_tool_ids: tuple[Identifier, ...] = ()


class UsageSummary(ExecutionContract):
    attempts: tuple[RunAttempt, ...]
    actual_micro_usd: int | None
    known_subtotal_micro_usd: int
    reserved_micro_usd: int
    unresolved_attempts: int
    coverage: Literal["bounded_1000_latest_attempt_records"] = "bounded_1000_latest_attempt_records"


class WorkflowRunRequest(ExecutionContract):
    policy: VersionRef
    inputs: dict[Identifier, JsonValue] = Field(repr=False)
    sample_reference: Identifier | None = None


class SandboxRun(ExecutionContract):
    id: Identifier
    policy: VersionRef
    status: Literal[
        "queued", "running", "awaiting_approval", "succeeded", "failed", "cancelled", "uncertain"
    ]
    created_at: AwareDatetime
    attempt_ids: tuple[Identifier, ...] = ()
    output_reference: Identifier | None = None
    quality: Literal["untested_provisional", "measured_not_production_approved"]
    environment: Literal["sandbox"] = "sandbox"


class RunStatusEvent(ExecutionContract):
    type: Literal["run.status"] = "run.status"
    run_id: Identifier
    sequence: int = Field(ge=1)
    run: SandboxRun

    @model_validator(mode="after")
    def identity(self) -> "RunStatusEvent":
        if self.run_id != self.run.id:
            raise ValueError("Event/run identity mismatch")
        return self


class RunUsageEvent(ExecutionContract):
    type: Literal["run.usage"] = "run.usage"
    run_id: Identifier
    sequence: int = Field(ge=1)
    usage: UsageReconciliation


class RunErrorEvent(ExecutionContract):
    type: Literal["run.error"] = "run.error"
    run_id: Identifier
    sequence: int = Field(ge=1)
    error: GatewayError


RunEvent = Annotated[RunStatusEvent | RunUsageEvent | RunErrorEvent, Field(discriminator="type")]


class ImportedSample(ExecutionContract):
    id: Identifier
    kind: Literal["sample", "trace"]
    inputs: dict[Identifier, JsonValue] = Field(repr=False)
    expected_output: JsonValue | None = Field(default=None, repr=False)
    observed_output: JsonValue | None = Field(default=None, repr=False)
    source_label: str = Field(min_length=1, max_length=200)
    original_observed_at: AwareDatetime | None = None
    imported_at: AwareDatetime
    data_class: Literal["synthetic", "tenant_private"]
    processing: Literal["local_only", "approved_hosted"] = "local_only"
    retention_days: int = Field(ge=1, le=30)
    provenance: Literal["user_imported_not_verified"] = "user_imported_not_verified"
    split: Literal["tuning", "holdout", "unspecified"] = "unspecified"
    output_schema: JsonSchema | None = None
    expected_reviewed: bool = False
    tool_schemas: tuple[ToolDefinition, ...] = Field(default=(), max_length=10)

    @model_validator(mode="after")
    def bounded(self) -> "ImportedSample":
        if len(self.model_dump_json().encode()) > 65536:
            raise ValueError("Import exceeds 64 KiB")
        if self.expected_reviewed and self.expected_output is None:
            raise ValueError("Reviewed expected answer required")
        return self


class StoredOutput(ExecutionContract):
    id: Identifier
    run_id: Identifier
    node_id: Identifier
    value: JsonValue = Field(repr=False)
    created_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def retention(self) -> "StoredOutput":
        if not 0 < (self.expires_at - self.created_at).total_seconds() <= 30 * 86400:
            raise ValueError("Output retention must be positive and at most 30 days")
        return self


class ComparisonRequest(ExecutionContract):
    sample_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=20)
    policies: tuple[VersionRef, ...] = Field(min_length=2, max_length=4)
    budget: ExecutionBudget

    @model_validator(mode="after")
    def distinct(self) -> "ComparisonRequest":
        if len(set(self.sample_ids)) != len(self.sample_ids) or len(
            {(p.id, p.version) for p in self.policies}
        ) != len(self.policies):
            raise ValueError("Comparison samples and pinned policies must be distinct")
        return self


class SampleCheck(ExecutionContract):
    check: Literal["json_schema", "reviewed_exact_match"]
    status: Literal["pass", "fail", "not_run"]
    detail: str


class ComparisonCell(ExecutionContract):
    sample_id: Identifier
    policy: VersionRef
    run_id: Identifier | None = None
    status: Literal["not_run", "completed", "failed", "blocked"]
    output_reference: Identifier | None = None
    usage: UsageReconciliation | None = None
    attempt_usages: tuple[UsageReconciliation, ...] = ()
    checks: tuple[SampleCheck, ...] = ()
    completion_ms: int | None = Field(default=None, ge=0)
    upstream_ms: int | None = Field(default=None, ge=0)
    gateway_overhead_ms: int | None = Field(default=None, ge=0)
    time_to_first_content_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def real_output(self) -> "ComparisonCell":
        if self.status == "completed" and (
            not self.run_id or not self.output_reference or not (self.usage or self.attempt_usages)
        ):
            raise ValueError("Completed comparison needs an actual run/output/usage record")
        return self


class ComparisonResult(ExecutionContract):
    id: Identifier
    request: ComparisonRequest
    cells: tuple[ComparisonCell, ...]
    quality_claim: Literal["exploratory_not_quality_validation"] = (
        "exploratory_not_quality_validation"
    )


class ExecutionSchemaBundle(ExecutionContract):
    """Generates every contract through the central OpenAPI schema, including SSE."""

    policy: PolicyView
    alias: RouteAlias
    admission: SandboxAdmission
    key: ApplicationKeyMetadata
    credential: ProviderCredentialReference
    chunk: ChatCompletionChunk
    event: RunEvent
    attempt: RunAttempt
    comparison: ComparisonResult
    target: TargetConfiguration
    output: StoredOutput
    grant: RuntimeGrant
    stream_observation: StreamObservation
    approved_endpoint: ApprovedEndpoint
    sample: ImportedSample
