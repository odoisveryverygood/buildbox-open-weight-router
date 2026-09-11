"""Central studio/gateway routes. Only approved composition dispatches inference.

Chat returns tool calls; the separate authorized worker owns workflow execution.
"""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import aclosing, suppress
from datetime import UTC, datetime, timedelta
from typing import NoReturn, cast
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from .contracts import ErrorCode
from .errors import DomainError
from .execution_contracts import (
    ApplicationKeyMetadata,
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ComparisonRequest,
    ComparisonResult,
    DecisionTrace,
    ExecutablePolicy,
    GatewayError,
    GatewayErrorDetail,
    ImportedSample,
    IssuedKey,
    KeyIssueRequest,
    ModelList,
    PolicyEditRequest,
    PolicyHistory,
    PolicyView,
    PromptRevision,
    RouteAlias,
    RunAttempt,
    RuntimeStatus,
    SandboxAdmission,
    SandboxRun,
    Scope,
    StoredOutput,
    TransitionRequest,
    UsageSummary,
    VariantRequest,
    VersionRef,
    WorkflowRunRequest,
)
from .execution_events import CHAT_DONE, chat_sse, run_sse
from .execution_ports import ExecutionServices, RequestContext
from .execution_security import authorize_application_key, authorize_sandbox, validate_inputs
from .execution_storage import SandboxStorage
from .storage import SqlStorage


def repository(request: Request) -> SandboxStorage:
    explicit = request.app.state.sandbox_storage
    if isinstance(explicit, SandboxStorage):
        return explicit
    storage = request.app.state.services.storage
    if not isinstance(storage, SqlStorage):
        raise DomainError(ErrorCode.UNSUPPORTED, "Sandbox durable storage unavailable", 503)
    return SandboxStorage(storage.engine)


studio = APIRouter(prefix="/api/studio", tags=["Sandbox studio v2"])


def runtime(request: Request) -> ExecutionServices:
    value = request.app.state.execution_services
    if value is None:
        unavailable()
    return cast(ExecutionServices, value)


async def context(
    request: Request,
    scope: Scope,
    *,
    alias: str | None = None,
    policy: ExecutablePolicy | None = None,
) -> RequestContext:
    services = runtime(request)
    now = datetime.now(UTC)
    key = None
    owner = request.state.owner
    bearer = request.headers.get("authorization", "")
    if request.url.path.startswith("/v1/") or bearer.startswith("Bearer "):
        if not bearer.startswith("Bearer ") or len(bearer) > 512:
            raise DomainError(ErrorCode.UNSUPPORTED, "Application key required", 401)
        key = await services.keys.authenticate(bearer[7:], now)
        owner = key.tenant_id
        authorize_application_key(owner, key, scope, now, alias=alias, policy=policy)
    request_id = uuid4().hex
    idempotency = request.headers.get("idempotency-key", request_id)
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", idempotency):
        raise DomainError(ErrorCode.INVALID, "Invalid idempotency key", 422)
    deadline = now + timedelta(seconds=120)

    def check() -> None:
        if datetime.now(UTC) >= deadline:
            raise DomainError(ErrorCode.UNSUPPORTED, "Request deadline elapsed", 408)

    return RequestContext(
        owner, key.id if key else owner, request_id, idempotency, deadline, check, key
    )


def enabled(request: Request, tenant: str, ref: VersionRef) -> ExecutablePolicy:
    store = repository(request)
    view = store.policy(tenant, ref)
    if not view.transition.admission_id:
        raise DomainError(ErrorCode.UNSUPPORTED, "Sandbox policy is not enabled", 403)
    admission = SandboxAdmission.model_validate_json(
        store.read(tenant, "admission", view.transition.admission_id)
    )
    authorize_sandbox(
        tenant,
        view.policy,
        view.transition,
        admission,
        datetime.now(UTC),
        allow_synthetic=store.offline_contract_test,
    )
    return view.policy


@studio.post("/policies", status_code=201)
def create_policy(value: ExecutablePolicy, request: Request) -> PolicyView:
    return repository(request).create_policy(request.state.owner, value)


@studio.get("/policies/{policy_id}/versions/{version}")
def get_policy(policy_id: str, version: int, request: Request) -> PolicyView:
    return repository(request).policy(
        request.state.owner, VersionRef(id=policy_id, version=version)
    )


@studio.post("/policies/{policy_id}/versions/{version}/variants", status_code=201)
def create_variant(
    policy_id: str, version: int, value: VariantRequest, request: Request
) -> PolicyView:
    from .execution_policy import variant
    from .planning_storage import PlanningStorage

    store = repository(request)
    policy = store.policy(request.state.owner, VersionRef(id=policy_id, version=version)).policy
    view = PlanningStorage(store.engine).view(
        request.state.owner, policy.plan.id, policy.plan.version
    )
    if not view.result or not view.result.catalog:
        raise DomainError(ErrorCode.CONFLICT, "Owned pinned planning catalog required", 409)
    catalog = view.result.catalog
    compiled = variant(policy, catalog, value, request.app.state.services.selector)
    return store.create_policy(request.state.owner, compiled)


@studio.post("/policies/{policy_id}/versions/{version}/propose-edit")
def propose_edit(
    policy_id: str, version: int, value: PolicyEditRequest, request: Request
) -> ExecutablePolicy:
    from .execution_policy import edit
    from .planning_storage import PlanningStorage

    store = repository(request)
    policy = store.policy(request.state.owner, VersionRef(id=policy_id, version=version)).policy
    plan = PlanningStorage(store.engine).view(
        request.state.owner, policy.plan.id, policy.plan.version
    )
    if not plan.result or not plan.result.catalog:
        raise DomainError(ErrorCode.CONFLICT, "Owned pinned planning catalog required", 409)
    return edit(policy, plan.result.catalog, value, request.app.state.services.selector)


@studio.get("/policies/{policy_id}/history")
def policy_history(policy_id: str, request: Request) -> PolicyHistory:
    store = repository(request)
    revision, _ = store.latest(request.state.owner, "policy", policy_id)
    return PolicyHistory(
        versions=tuple(
            VersionRef(id=policy_id, version=v) for v in range(max(1, revision - 99), revision + 1)
        )
    )


@studio.post("/policies/{policy_id}/versions/{version}/transitions")
def transition(
    policy_id: str, version: int, value: TransitionRequest, request: Request
) -> PolicyView:
    return repository(request).transition(
        request.state.owner, VersionRef(id=policy_id, version=version), value
    )


@studio.post("/aliases", status_code=201)
def create_alias(value: RouteAlias, request: Request) -> RouteAlias:
    return repository(request).create_alias(request.state.owner, value)


@studio.get("/aliases/{alias_id}")
def get_alias(alias_id: str, request: Request) -> RouteAlias:
    return repository(request).alias(request.state.owner, alias_id)


@studio.post("/prompts", status_code=201)
def save_prompt(value: PromptRevision, request: Request) -> PromptRevision:
    return repository(request).save_prompt(request.state.owner, value)


@studio.get("/prompts/{prompt_id}/versions/{version}")
def get_prompt(prompt_id: str, version: int, request: Request) -> PromptRevision:
    return PromptRevision.model_validate_json(
        repository(request).read(request.state.owner, "prompt", prompt_id, version)
    )


@studio.post("/imports", status_code=201)
def import_sample(value: ImportedSample, request: Request) -> ImportedSample:
    # Replace client import timestamp: it is not a source measurement date.
    value = ImportedSample.model_validate(value.model_dump() | {"imported_at": datetime.now(UTC)})
    return repository(request).import_sample(request.state.owner, value)


@studio.get("/imports/{sample_id}")
def get_sample(sample_id: str, request: Request) -> ImportedSample:
    return repository(request).sample(request.state.owner, sample_id)


@studio.get("/outputs/{output_id}")
def get_output(output_id: str, request: Request) -> StoredOutput:
    return repository(request).output(request.state.owner, output_id)


@studio.get("/traces/{request_id}")
def get_trace(request_id: str, request: Request) -> DecisionTrace:
    return repository(request).trace(request.state.owner, request_id)


@studio.get("/runtime")
def runtime_status(request: Request) -> RuntimeStatus:
    installed = request.app.state.execution_services is not None
    from .execution_jobs import QueuedWorkflows

    flows = request.app.state.execution_services.workflows if installed else None
    tool_ids = (
        tuple(
            sorted(
                tool for tenant, tool in flows.runner.tools.tables if tenant == request.state.owner
            )
        )
        if isinstance(flows, QueuedWorkflows)
        else ()
    )
    return RuntimeStatus(
        installed=installed,
        mode="synthetic_test"
        if installed and repository(request).offline_contract_test
        else "approved"
        if installed
        else "disabled",
        target_count=None,
        available_tool_ids=tool_ids,
        detail="Runtime composed; each request requires current operator admission. LIVE INFERENCE NOT VERIFIED"
        if installed
        else "No approved runtime registry configured. LIVE INFERENCE NOT VERIFIED",
    )


@studio.get("/usage")
def usage_summary(
    request: Request, route: str = "", since: str = "", until: str = ""
) -> UsageSummary:
    rows = [
        RunAttempt.model_validate_json(raw)
        for raw in repository(request).records(request.state.owner, "attempt")
    ]
    rows = [
        a
        for a in rows
        if (not route or a.trace.alias_id == route or a.trace.policy.id == route)
        and (not since or a.usage.observed_at.date().isoformat() >= since)
        and (not until or a.usage.observed_at.date().isoformat() <= until)
    ]
    subtotal = sum(a.usage.actual_micro_usd or 0 for a in rows)
    unresolved = sum(a.usage.actual_micro_usd is None for a in rows)
    return UsageSummary(
        attempts=tuple(rows),
        actual_micro_usd=None if unresolved else subtotal,
        known_subtotal_micro_usd=subtotal,
        reserved_micro_usd=sum(a.usage.reserved_micro_usd for a in rows),
        unresolved_attempts=unresolved,
    )


@studio.post("/keys", status_code=201)
async def issue_key(value: KeyIssueRequest, request: Request) -> IssuedKey:
    ctx = await context(request, "models:read")
    metadata, secret = runtime(request).keys.issue(
        ctx,
        expires_at=value.expires_at,
        scopes=value.scopes,
        aliases=value.alias_ids,
        policies=value.workflow_policies,
        max_cost_micro_usd=value.max_cost_micro_usd,
    )
    return IssuedKey(metadata=metadata, secret=secret)


@studio.get("/keys")
def keys(request: Request) -> tuple[ApplicationKeyMetadata, ...]:
    return tuple(
        ApplicationKeyMetadata.model_validate_json(v)
        for v in repository(request).records(request.state.owner, "application_key")
    )


@studio.post("/keys/{key_id}/revoke")
async def revoke_key(key_id: str, request: Request) -> ApplicationKeyMetadata:
    return await runtime(request).keys.revoke(await context(request, "models:read"), key_id)


@studio.get("/runs")
def studio_runs(request: Request) -> tuple[SandboxRun, ...]:
    store = repository(request)
    values = (SandboxRun.model_validate_json(v) for v in store.records(request.state.owner, "run"))
    return tuple(
        SandboxRun.model_validate(
            v.model_dump() | {"status": store.request_state(request.state.owner, v.id)}
        )
        for v in values
    )


@studio.get("/runs/{run_id}/attempts")
async def attempts(run_id: str, request: Request) -> tuple[RunAttempt, ...]:
    ctx = await context(request, "runs:read")
    await runtime(request).workflows.get(ctx, run_id)
    return repository(request).attempts(ctx.tenant_id, run_id)


def unavailable() -> NoReturn:
    raise DomainError(
        ErrorCode.UNSUPPORTED, "Sandbox runtime port not installed; no execution occurred", 503
    )


@studio.post("/comparisons", status_code=202)
async def compare(value: ComparisonRequest, request: Request) -> ComparisonResult:
    ctx = await context(request, "workflow:run")
    for ref in value.policies:
        enabled(request, ctx.tenant_id, ref)
    return await runtime(request).comparisons.submit(ctx, value)


@studio.get("/comparisons/{comparison_id}")
async def get_comparison(comparison_id: str, request: Request) -> ComparisonResult:
    return await runtime(request).comparisons.get(
        await context(request, "runs:read"), comparison_id
    )


workflow_routes = APIRouter(prefix="/api/sandbox", tags=["Sandbox workflow runs v2"])

# Keep a separate workflow endpoint; Chat Completions NEVER invokes this port.


@workflow_routes.post("/runs", status_code=202)
async def run_workflow(value: WorkflowRunRequest, request: Request) -> SandboxRun:
    ctx = await context(request, "workflow:run")
    policy = enabled(request, ctx.tenant_id, value.policy)
    if ctx.application_key:
        authorize_application_key(
            ctx.tenant_id, ctx.application_key, "workflow:run", datetime.now(UTC), policy=policy
        )
    validate_inputs(policy.input_types, value.inputs)
    return await runtime(request).workflows.submit(ctx, value)


@workflow_routes.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> SandboxRun:
    return await runtime(request).workflows.get(await context(request, "runs:read"), run_id)


@workflow_routes.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str, request: Request) -> SandboxRun:
    return await runtime(request).workflows.cancel(await context(request, "runs:cancel"), run_id)


@workflow_routes.get("/runs/{run_id}/outputs/{output_id}")
async def run_output(run_id: str, output_id: str, request: Request) -> StoredOutput:
    ctx = await context(request, "runs:read")
    await runtime(request).workflows.get(ctx, run_id)
    value = repository(request).output(ctx.tenant_id, output_id)
    if value.run_id != run_id:
        raise DomainError(ErrorCode.NOT_FOUND, "Output is not part of this run", 404)
    return value


@workflow_routes.get("/runs/{run_id}/outputs")
async def run_outputs(run_id: str, request: Request) -> tuple[StoredOutput, ...]:
    ctx = await context(request, "runs:read")
    await runtime(request).workflows.get(ctx, run_id)
    return repository(request).outputs_for_run(ctx.tenant_id, run_id)


@workflow_routes.get("/traces/{request_id}")
async def runtime_trace(request_id: str, request: Request) -> DecisionTrace:
    ctx = await context(request, "runs:read")
    value = repository(request).trace(ctx.tenant_id, request_id)
    if ctx.application_key:
        policy = (
            None
            if value.alias_id
            else repository(request).policy(ctx.tenant_id, value.policy).policy
        )
        authorize_application_key(
            ctx.tenant_id,
            ctx.application_key,
            "runs:read",
            datetime.now(UTC),
            alias=value.alias_id,
            policy=policy,
        )
    return value


@workflow_routes.get(
    "/runs/{run_id}/events",
    response_class=JSONResponse,
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": {
                        "oneOf": [
                            {"$ref": "#/components/schemas/RunStatusEvent"},
                            {"$ref": "#/components/schemas/RunUsageEvent"},
                            {"$ref": "#/components/schemas/RunErrorEvent"},
                        ]
                    }
                }
            }
        }
    },
)
async def run_events(run_id: str, request: Request, after_sequence: int = 0) -> StreamingResponse:
    if not 0 <= after_sequence <= 10000:
        raise DomainError(ErrorCode.INVALID, "Event cursor outside bounds", 422)
    ctx = await context(request, "runs:read")
    await runtime(request).workflows.get(ctx, run_id)  # tenant check before headers

    async def stream() -> AsyncIterator[str]:
        async for event in runtime(request).workflows.events(ctx, run_id, after_sequence):
            if await request.is_disconnected():
                return
            yield run_sse(event)

    return StreamingResponse(
        stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"}
    )


gateway = APIRouter(
    prefix="/v1",
    tags=["Chat Completions compatible SUBSET"],
    responses={
        code: {"model": GatewayError}
        for code in (400, 401, 403, 404, 408, 409, 413, 422, 429, 500, 502, 503)
    },
)


def gateway_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=GatewayError(
            error=GatewayErrorDetail(
                type="server_error",
                code="runtime_unavailable",
                message="Sandbox gateway port not installed; no inference occurred",
            )
        ).model_dump(),
    )


def gateway_failure(status: int) -> JSONResponse:
    kind, code = {
        401: ("authentication_error", "unauthorized"),
        403: ("permission_error", "admission_denied"),
        408: ("server_error", "timeout"),
        429: ("rate_limit_error", "budget_exhausted"),
        500: ("server_error", "accounting_uncertain"),
        503: ("server_error", "runtime_unavailable"),
    }.get(status, ("invalid_request_error", "invalid_request"))
    error = GatewayError.model_validate(
        {
            "error": {
                "type": kind,
                "code": code,
                "message": "Sandbox request failed; inspect request status before retrying",
            }
        }
    )
    return JSONResponse(status_code=status, content=error.model_dump())


@gateway.get("/models", response_model=ModelList)
async def models(request: Request) -> JSONResponse:
    if request.app.state.execution_services is None:
        return gateway_unavailable()
    ctx = await context(request, "models:read")
    value = await runtime(request).gateway.models(ctx)
    assert ctx.application_key is not None
    value = ModelList(
        data=tuple(row for row in value.data if row.id in ctx.application_key.alias_ids)
    )
    return JSONResponse(value.model_dump())


@gateway.post(
    "/chat/completions",
    response_model=ChatCompletion,
    responses={
        200: {
            "content": {
                "text/event-stream": {
                    "schema": {"$ref": "#/components/schemas/ChatCompletionChunk"}
                }
            }
        }
    },
)
async def complete(
    value: ChatCompletionRequest, request: Request
) -> JSONResponse | StreamingResponse:
    if request.app.state.execution_services is None:
        return gateway_unavailable()
    ctx = await context(request, "chat:complete", alias=value.model)
    alias = repository(request).alias(ctx.tenant_id, value.model)
    policy = enabled(request, ctx.tenant_id, alias.policy)
    stage = next(s for s in policy.stages if s.node_id == alias.node_id)
    if value.max_tokens > stage.budget.max_output_tokens:
        raise DomainError(
            ErrorCode.UNSUPPORTED, "Requested output exceeds pinned stage budget", 403
        )
    headers = {"X-Request-ID": ctx.request_id, "X-Buildbox-Quality": policy.quality}
    if value.stream:
        source = runtime(request).gateway.stream(ctx, value)
        # Resolve/preflight and obtain the first event before committing HTTP headers.
        # There is still no replay after the first response delta is delivered.
        pending_first = asyncio.create_task(anext(source))

        async def disconnected_before_headers() -> None:
            while not pending_first.done():
                if await request.is_disconnected():
                    pending_first.cancel()
                    return
                await asyncio.sleep(0.05)

        watcher = asyncio.create_task(disconnected_before_headers())
        try:
            first = await pending_first
        finally:
            watcher.cancel()
            with suppress(asyncio.CancelledError):
                await watcher
        if isinstance(first, GatewayError):
            await source.aclose()
            return JSONResponse(first.model_dump(), status_code=502, headers=headers)

        async def stream() -> AsyncIterator[str]:
            try:
                finished = False
                async with aclosing(source):
                    chunk: ChatCompletionChunk | GatewayError = first
                    while True:
                        if await request.is_disconnected():
                            return
                        if isinstance(chunk, ChatCompletionChunk) and chunk.model != value.model:
                            raise ValueError("Alias identity mismatch")
                        if isinstance(chunk, ChatCompletionChunk):
                            finished = finished or any(
                                c.finish_reason is not None for c in chunk.choices
                            )
                        yield chat_sse(chunk)
                        if isinstance(chunk, GatewayError):
                            return
                        try:
                            chunk = await anext(source)
                        except StopAsyncIteration:
                            break
                if not finished:
                    raise ValueError("Stream ended without a terminal model event")
                yield CHAT_DONE
            except Exception:
                yield chat_sse(
                    GatewayError(
                        error=GatewayErrorDetail(
                            type="server_error",
                            code="partial_failure",
                            message="Stream interrupted; inspect request usage before retrying",
                        )
                    )
                )

        return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)
    response = await runtime(request).gateway.complete(ctx, value)
    if response.model != value.model:
        raise DomainError(ErrorCode.CONFLICT, "Alias response mismatch", 409)
    return JSONResponse(response.model_dump(exclude_none=True), headers=headers)
