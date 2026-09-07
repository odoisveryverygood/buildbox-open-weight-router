"""Frozen Lane 7/8 boundary. Implementations are composed only by integration.

No lane imports a sibling implementation. Tenant/principal comes from verified
server auth, never request JSON. No default implementation executes a model.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from pydantic import JsonValue

from .execution_contracts import (
    ApplicationKeyMetadata,
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ComparisonRequest,
    ComparisonResult,
    CompletionUsage,
    DecisionTrace,
    ExecutionBudget,
    GatewayError,
    ImportedSample,
    ModelList,
    ProviderCredentialReference,
    RouteAlias,
    RunEvent,
    SandboxRun,
    TargetConfiguration,
    VersionRef,
    WorkflowRunRequest,
)


@dataclass(frozen=True)
class RequestContext:
    tenant_id: str
    principal_id: str
    request_id: str
    idempotency_key: str
    deadline: datetime
    check_cancelled: Callable[[], None]
    application_key: ApplicationKeyMetadata | None = None


@dataclass(frozen=True)
class InferenceCall:
    trace: DecisionTrace
    credential: ProviderCredentialReference
    messages: ChatCompletionRequest
    budget: ExecutionBudget
    reservation_id: str
    target: TargetConfiguration
    # Trace pins configuration + endpoint; messages.model is never sent as provider ID.


@dataclass(frozen=True)
class InferenceResult:
    completion: ChatCompletion
    actual_micro_usd: int | None
    usage: CompletionUsage | None
    trace: DecisionTrace


class RuntimeInferencePort(Protocol):
    async def complete(self, context: RequestContext, call: InferenceCall) -> InferenceResult: ...
    def stream(
        self, context: RequestContext, call: InferenceCall
    ) -> AsyncIterator[ChatCompletionChunk | GatewayError]: ...


class GatewayPort(Protocol):
    async def models(self, context: RequestContext) -> ModelList: ...
    async def complete(
        self, context: RequestContext, value: ChatCompletionRequest
    ) -> ChatCompletion: ...
    def stream(
        self, context: RequestContext, value: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk | GatewayError]: ...


class WorkflowRunnerPort(Protocol):
    async def submit(self, context: RequestContext, value: WorkflowRunRequest) -> SandboxRun: ...
    async def get(self, context: RequestContext, run_id: str) -> SandboxRun: ...
    async def cancel(self, context: RequestContext, run_id: str) -> SandboxRun: ...
    def events(
        self, context: RequestContext, run_id: str, after_sequence: int
    ) -> AsyncIterator[RunEvent]: ...


class ToolDispatcherPort(Protocol):
    async def dispatch(
        self,
        context: RequestContext,
        tool_id: str,
        inputs: dict[str, JsonValue],
        budget: ExecutionBudget,
    ) -> dict[str, JsonValue]: ...


class ApplicationKeyPort(Protocol):
    async def authenticate(self, bearer: str, now: datetime) -> ApplicationKeyMetadata: ...
    async def revoke(self, context: RequestContext, key_id: str) -> ApplicationKeyMetadata: ...


class ComparisonPort(Protocol):
    async def submit(
        self, context: RequestContext, value: ComparisonRequest
    ) -> ComparisonResult: ...
    async def get(self, context: RequestContext, comparison_id: str) -> ComparisonResult: ...


class StudioRepositoryPort(Protocol):
    def import_sample(self, tenant: str, value: ImportedSample) -> ImportedSample: ...
    def sample(self, tenant: str, sample_id: str) -> ImportedSample: ...
    def alias(self, tenant: str, alias_id: str) -> RouteAlias: ...
    def trace(self, tenant: str, request_id: str) -> DecisionTrace: ...
    def policy_exists(self, tenant: str, policy: VersionRef) -> bool: ...


@dataclass(frozen=True)
class ExecutionServices:
    """Explicit integration injection. No default/fixture/live service is auto-selected."""

    gateway: GatewayPort
    workflows: WorkflowRunnerPort
    keys: ApplicationKeyPort
    comparisons: ComparisonPort
