"""Durable alias-pinned gateway; zero retries, no business tool execution."""

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from ..contracts import ErrorCode
from ..errors import DomainError
from ..execution_contracts import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatMessage,
    GatewayError,
    GatewayErrorDetail,
    ModelList,
    ModelListing,
    RunAttempt,
    StoredOutput,
    UsageReconciliation,
)
from ..execution_ports import InferenceCall, InferenceResult, RequestContext, RuntimeInferencePort
from ..execution_security import validate_alias
from .keys import ApplicationKeys
from .preflight import Authority, AuthorizedStage, preflight


def fingerprint(*parts: object) -> str:
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def failure(*, partial: bool = False) -> GatewayError:
    return GatewayError(
        error=GatewayErrorDetail(
            type="server_error",
            code="accounting_uncertain",
            message=(
                "Partial failure after output; no replay or model substitution. Usage pending."
                if partial
                else "Inference failed; no replay attempted. Usage may remain pending."
            ),
        )
    )


class Gateway:
    def __init__(
        self,
        authority: Authority,
        inference: RuntimeInferencePort,
        keys: ApplicationKeys,
        *,
        retain_seconds: int = 0,
        streaming_enabled: bool = False,
    ) -> None:
        if not 0 <= retain_seconds <= 30 * 86400:
            raise ValueError("Invalid explicit retention")
        self.authority, self.inference, self.keys = authority, inference, keys
        self.store, self.retain_seconds = authority.store, retain_seconds
        self.streaming_enabled = streaming_enabled

    async def models(self, context: RequestContext) -> ModelList:
        key = self.keys.check(context, "models:read")
        rows = []
        for name in sorted(key.alias_ids):
            try:
                alias = self.store.alias(context.tenant_id, name)
                authorized = self.authority.stage(context, alias.policy, alias.node_id, alias=name)
                preflight(
                    authorized,
                    ChatCompletionRequest(
                        model=name,
                        messages=(ChatMessage(role="user", content="Capability preflight"),),
                        max_tokens=1,
                    ),
                )
                rows.append(ModelListing(id=name, created=int(alias.created_at.timestamp())))
            except DomainError:
                continue  # Do not list unavailable or inaccessible aliases.
        return ModelList(data=tuple(rows))

    def prepare(
        self, context: RequestContext, value: ChatCompletionRequest
    ) -> tuple[RequestContext, AuthorizedStage, ChatCompletionRequest, bool]:
        self.keys.check(context, "chat:complete", alias=value.model)  # BEFORE alias lookup.
        alias = self.store.alias(context.tenant_id, value.model)
        authorized = self.authority.stage(context, alias.policy, alias.node_id, alias=alias.id)
        validate_alias(authorized.policy, alias)
        prompt = next(
            p
            for p in authorized.policy.prompts
            if authorized.stage.prompt
            and (p.id, p.version) == (authorized.stage.prompt.id, authorized.stage.prompt.version)
        )
        # Generic chat accepts text history, not typed DAG variable values. The pinned
        # template is the stage instruction; runner uses fully rendered variables.
        messages = (ChatMessage(role="system", content=prompt.template),) + tuple(
            ChatMessage(role="user" if m.role == "system" else m.role, content=m.content)
            for m in value.messages
        )
        outgoing = ChatCompletionRequest.model_validate(value.model_dump() | {"messages": messages})
        preflight(authorized, outgoing)
        hashed = fingerprint(
            "chat",
            context.principal_id,
            alias.model_dump(mode="json"),
            authorized.policy.model_dump(mode="json"),
            value.model_dump(mode="json"),
        )
        identifier, created = self.store.register_request(
            context.tenant_id, context.idempotency_key, context.request_id, hashed
        )
        return replace(context, request_id=identifier), authorized, outgoing, created

    def start(
        self,
        context: RequestContext,
        value: AuthorizedStage,
        request: ChatCompletionRequest,
        run_id: str,
    ) -> tuple[InferenceCall, RunAttempt]:
        context.check_cancelled()
        amount = preflight(value, request)
        if context.application_key:
            self.keys.reserve(context, amount)
        reservation = "call-" + context.request_id
        self.store.reserve(
            context.tenant_id,
            value.admission.budget_reference,
            reservation,
            context.request_id,
            amount,
        )
        trace = value.trace.model_copy(update={"request_id": context.request_id})
        usage = UsageReconciliation(
            reservation_id=reservation,
            reserved_micro_usd=amount,
            state="reserved",
            observed_at=datetime.now(UTC),
        )
        attempt = RunAttempt(
            id=context.request_id,
            run_id=run_id,
            node_id=value.stage.node_id,
            status="reserved",
            trace=trace,
            usage=usage,
        )
        self.store.save_attempt(context.tenant_id, attempt, 1)
        call = InferenceCall(
            trace, value.credential, request, value.stage.budget, reservation, value.target
        )
        return call, attempt

    def finish(
        self,
        context: RequestContext,
        attempt: RunAttempt,
        result: InferenceResult | None,
        *,
        cancelled: bool = False,
        partial: bool = False,
    ) -> RunAttempt:
        actual = result.actual_micro_usd if result else None
        overage = actual is not None and actual > attempt.usage.reserved_micro_usd
        self.store.reconcile(context.tenant_id, attempt.usage.reservation_id, actual)
        if context.application_key:
            self.store.reconcile(context.tenant_id, "key-" + context.request_id, actual)
        if overage:
            actual = None
        usage = UsageReconciliation(
            reservation_id=attempt.usage.reservation_id,
            reserved_micro_usd=attempt.usage.reserved_micro_usd,
            actual_micro_usd=actual,
            state="reconciled" if actual is not None else "uncertain",
            tokens=result.usage if result else None,
            observed_at=datetime.now(UTC),
        )
        trace = result.trace if result else attempt.trace
        # Adapters may add observations, never alter a control-plane pin.
        pinned = {"served_model", "served_endpoint"}
        if trace.model_dump(exclude=pinned) != attempt.trace.model_dump(exclude=pinned):
            raise DomainError(ErrorCode.CONFLICT, "Adapter changed a decision pin", 500)
        self.store.save_trace(context.tenant_id, trace)
        done = attempt.model_copy(
            update={
                "status": "cancelled"
                if cancelled
                else "succeeded"
                if result and actual is not None
                else "uncertain",
                "usage": usage,
                "trace": trace,
                "error": None if result and not overage else failure(partial=partial),
            }
        )
        self.store.save_attempt(context.tenant_id, done, 3)
        return done

    async def infer(
        self,
        context: RequestContext,
        authorized: AuthorizedStage,
        request: ChatCompletionRequest,
        run_id: str,
    ) -> tuple[InferenceResult, RunAttempt]:
        # A bounded callback is checked by shared transports between socket reads.
        deadline = min(
            context.deadline,
            datetime.now(UTC) + timedelta(milliseconds=authorized.stage.budget.timeout_ms),
        )
        original = context

        def check() -> None:
            original.check_cancelled()
            if datetime.now(UTC) >= deadline:
                raise TimeoutError("Sandbox stage deadline")

        context = replace(context, deadline=deadline, check_cancelled=check)
        call, attempt = self.start(context, authorized, request, run_id)
        try:
            check()
            # Recheck current policy/credentials immediately before dispatch.
            fresh = self.authority.stage(
                context,
                call.trace.policy,
                call.trace.node_id,
                alias=call.trace.alias_id,
                data_class=authorized.data_class,
            )
            if fresh.target != authorized.target or fresh.credential != authorized.credential:
                raise ValueError("Endpoint or credential changed before dispatch")
            self.store.save_attempt(
                context.tenant_id, attempt.model_copy(update={"status": "dispatched"}), 2
            )
            async with asyncio.timeout(max(0, (deadline - datetime.now(UTC)).total_seconds())):
                result = await self.inference.complete(context, call)
            check()
            if result.completion.model != request.model or result.completion.usage != result.usage:
                raise ValueError("Response identity/usage mismatch")
            if result.usage and (
                result.usage.completion_tokens > request.max_tokens
                or result.usage.prompt_tokens > authorized.stage.budget.max_input_tokens
            ):
                raise ValueError("Observed tokens exceeded dispatch bounds")
            done = self.finish(context, attempt, result)
            if done.error:
                raise DomainError(ErrorCode.UNSUPPORTED, "Accounting bound violated", 500)
            return result, done
        except (asyncio.CancelledError, Exception) as error:
            # A dispatched request is never automatically refunded or restarted.
            try:
                self.store.latest(context.tenant_id, "trace", context.request_id)
            except DomainError:
                self.finish(
                    context, attempt, None, cancelled=isinstance(error, asyncio.CancelledError)
                )
            if isinstance(error, asyncio.CancelledError):
                raise
            raise DomainError(
                ErrorCode.UNSUPPORTED, "Inference failed; inspect pending accounting", 503
            ) from None

    async def complete(
        self, context: RequestContext, value: ChatCompletionRequest
    ) -> ChatCompletion:
        context, authorized, outgoing, created = self.prepare(context, value)
        if not created:
            if (
                self.retain_seconds
                and self.store.request_state(context.tenant_id, context.request_id) == "succeeded"
            ):
                return ChatCompletion.model_validate(
                    self.store.output(context.tenant_id, context.request_id).value
                )
            raise DomainError(
                ErrorCode.CONFLICT,
                "Request already registered; no redispatch. Content replay not retained or completion pending",
                409,
            )
        self.store.advance_request(context.tenant_id, context.request_id, "queued", "running")
        try:
            result, attempt = await self.infer(context, authorized, outgoing, context.request_id)
            if self.retain_seconds:
                now = datetime.now(UTC)
                self.store.save_output(
                    context.tenant_id,
                    StoredOutput(
                        id=context.request_id,
                        run_id=context.request_id,
                        node_id=authorized.stage.node_id,
                        value=result.completion.model_dump(mode="json"),
                        created_at=now,
                        expires_at=now + timedelta(seconds=self.retain_seconds),
                    ),
                )
            self.store.advance_request(
                context.tenant_id,
                context.request_id,
                "running",
                "succeeded" if attempt.usage.actual_micro_usd is not None else "uncertain",
            )
            return result.completion
        except BaseException:
            if self.store.request_state(context.tenant_id, context.request_id) == "running":
                self.store.advance_request(
                    context.tenant_id, context.request_id, "running", "uncertain"
                )
            raise

    async def stream(
        self, context: RequestContext, value: ChatCompletionRequest
    ) -> AsyncIterator[ChatCompletionChunk | GatewayError]:
        if not self.streaming_enabled:
            raise DomainError(
                ErrorCode.UNSUPPORTED,
                "Guarded streaming transport not installed; no upstream work",
                503,
            )
        context, authorized, outgoing, created = self.prepare(context, value)
        if not created:
            raise DomainError(ErrorCode.CONFLICT, "Stream already submitted; no replay", 409)
        self.store.advance_request(context.tenant_id, context.request_id, "queued", "running")
        try:
            call, attempt = self.start(context, authorized, outgoing, context.request_id)
        except Exception:
            self.store.advance_request(context.tenant_id, context.request_id, "running", "failed")
            raise
        exposed = False
        terminal = False
        observed = None
        output_bytes = 0
        try:
            self.keys.check(context, "chat:complete", alias=value.model)
            fresh = self.authority.stage(
                context, call.trace.policy, call.trace.node_id, alias=value.model
            )
            if fresh.target != authorized.target or fresh.credential != authorized.credential:
                raise ValueError("Endpoint or credential changed before stream dispatch")
            self.store.save_attempt(
                context.tenant_id, attempt.model_copy(update={"status": "dispatched"}), 2
            )
            async with asyncio.timeout(
                min(
                    authorized.stage.budget.timeout_ms / 1000,
                    max(0, (context.deadline - datetime.now(UTC)).total_seconds()),
                )
            ):
                async for chunk in self.inference.stream(context, call):
                    context.check_cancelled()
                    self.keys.check(context, "chat:complete", alias=value.model)
                    self.authority.policy(context, call.trace.policy)
                    if isinstance(chunk, GatewayError) or chunk.model != value.model:
                        raise ValueError("Stream error or alias mismatch")
                    choice = chunk.choices[0]
                    output_bytes += len((choice.delta.content or "").encode())
                    if output_bytes > 1048576:
                        raise ValueError("Stream output bound exceeded")
                    if terminal and choice.delta.content:
                        raise ValueError("Output after terminal event")
                    terminal = terminal or choice.finish_reason is not None
                    if chunk.usage:
                        if observed is not None and observed != chunk.usage:
                            raise ValueError("Conflicting usage observations")
                        observed = chunk.usage
                    # Accounting must persist before downstream success terminal.
                    if choice.finish_reason is None:
                        exposed = (
                            exposed
                            or choice.delta.content is not None
                            or choice.delta.role is not None
                        )
                        yield chunk
                    else:
                        if choice.delta.content:
                            exposed = True
                            yield chunk.model_copy(
                                update={
                                    "choices": (choice.model_copy(update={"finish_reason": None}),)
                                }
                            )
                        final = chunk.model_copy(
                            update={
                                "choices": (
                                    choice.model_copy(
                                        update={
                                            "delta": choice.delta.model_copy(
                                                update={"content": None}
                                            )
                                        }
                                    ),
                                )
                            }
                        )
                if not terminal:
                    raise ValueError("Stream missing finish reason")
                # Frozen stream port has no actual-cost or served-identity channel.
                # Retain the full hold and known tokens, never invent actual=0.
                done = self.finish(context, attempt, None)
                if observed is not None:
                    self.store.save_attempt(
                        context.tenant_id,
                        done.model_copy(
                            update={"usage": done.usage.model_copy(update={"tokens": observed})}
                        ),
                        4,
                    )
                self.store.advance_request(
                    context.tenant_id, context.request_id, "running", "uncertain"
                )
                yield final
        except (GeneratorExit, asyncio.CancelledError, Exception) as error:
            if self.store.request_state(context.tenant_id, context.request_id) == "running":
                self.finish(context, attempt, None, partial=exposed)
                self.store.advance_request(
                    context.tenant_id, context.request_id, "running", "uncertain"
                )
            if isinstance(error, (GeneratorExit, asyncio.CancelledError)):
                raise
            yield failure(partial=exposed)
