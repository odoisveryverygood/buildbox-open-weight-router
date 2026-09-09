"""Durable alias-pinned gateway; zero retries, no business tool execution."""

import asyncio
import hashlib
import json
from collections.abc import AsyncGenerator
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
    NamedToolChoice,
    RunAttempt,
    StoredOutput,
    StreamObservation,
    UsageReconciliation,
)
from ..execution_ports import InferenceCall, InferenceResult, RequestContext, RuntimeInferencePort
from ..execution_security import validate_alias
from ..json_contracts import parse_json
from .keys import ApplicationKeys
from .preflight import Authority, AuthorizedStage, preflight


def validate_completion(request: ChatCompletionRequest, response: ChatCompletion) -> None:
    choice = response.choices[0]
    message = choice.message
    calls = message.tool_calls or ()
    definitions = {t.function.name: t.function for t in request.tools or ()}
    if len({c.id for c in calls}) != len(calls):
        raise ValueError("Duplicate returned tool call IDs")
    if (choice.finish_reason == "tool_calls") != bool(calls):
        raise ValueError("Tool finish reason mismatch")
    if request.tool_choice == "none" and calls:
        raise ValueError("Unexpected tool calls")
    if (
        request.tool_choice == "required" or isinstance(request.tool_choice, NamedToolChoice)
    ) and not calls:
        raise ValueError("Required tool not returned")
    for call in calls:
        if call.function.name not in definitions:
            raise ValueError("Returned tool was not requested")
        if (
            isinstance(request.tool_choice, NamedToolChoice)
            and call.function.name != request.tool_choice.function.name
        ):
            raise ValueError("Returned tool differs from required choice")
        definitions[call.function.name].parameters.validate_value(
            parse_json(call.function.arguments)
        )
    if request.response_format and request.response_format.type != "text":
        if choice.finish_reason != "stop" or message.content is None:
            raise ValueError("Structured output did not complete")
        parsed = parse_json(message.content)
        if request.response_format.type == "json_object" and not isinstance(parsed, dict):
            raise ValueError("JSON object response required")
        if request.response_format.json_schema:
            request.response_format.json_schema.schema_.validate_value(parsed)


def fingerprint(*parts: object) -> str:
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def failure(*, partial: bool = False) -> GatewayError:
    return GatewayError(
        error=GatewayErrorDetail(
            type="server_error",
            code="partial_failure" if partial else "accounting_uncertain",
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
        if authorized.stage.fallback_configuration_ids and (value.tools or len(value.messages) > 1):
            raise DomainError(
                ErrorCode.UNSUPPORTED,
                "Conversation/tool sessions require a single-configuration alias; implicit repinning is forbidden",
                403,
            )
        prompt = next(
            p
            for p in authorized.policy.prompts
            if authorized.stage.prompt
            and (p.id, p.version) == (authorized.stage.prompt.id, authorized.stage.prompt.version)
        )
        # Generic chat accepts text history, not typed DAG variable values. The pinned
        # template is the stage instruction; runner uses fully rendered variables.
        messages = (ChatMessage(role="system", content=prompt.template),) + tuple(
            m.model_copy(update={"role": "user"}) if m.role == "system" else m
            for m in value.messages
        )
        outgoing = ChatCompletionRequest.model_validate(value.model_dump() | {"messages": messages})
        self.candidates(context, authorized, outgoing)
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

    def candidates(
        self, context: RequestContext, authorized: AuthorizedStage, request: ChatCompletionRequest
    ) -> tuple[AuthorizedStage, ...]:
        values = (authorized,) + tuple(
            self.authority.stage(
                context,
                authorized.trace.policy,
                authorized.stage.node_id,
                alias=authorized.trace.alias_id,
                data_class=authorized.data_class,
                configuration_id=c,
            )
            for c in authorized.stage.fallback_configuration_ids
        )
        if sum(preflight(a, request) for a in values) > authorized.stage.budget.max_cost_micro_usd:
            raise DomainError(
                ErrorCode.UNSUPPORTED, "Aggregate fallback envelope exceeds stage cap", 429
            )
        return values

    def start(
        self,
        context: RequestContext,
        value: AuthorizedStage,
        request: ChatCompletionRequest,
        run_id: str,
        attempt_number: int = 1,
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
            attempt=attempt_number,
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
        failed: bool = False,
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
                else "failed"
                if failed and actual is not None
                else "succeeded"
                if result and actual is not None
                else "uncertain",
                "usage": usage,
                "trace": trace,
                "latency_ms": max(
                    0, int((datetime.now(UTC) - attempt.usage.observed_at).total_seconds() * 1000)
                ),
                "error": None
                if result and not overage and not failed
                else failure(partial=partial),
            }
        )
        self.store.save_attempt(context.tenant_id, done, 3)
        return done

    async def _infer_once(
        self,
        context: RequestContext,
        authorized: AuthorizedStage,
        request: ChatCompletionRequest,
        run_id: str,
        attempt_number: int = 1,
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
        call, attempt = self.start(context, authorized, request, run_id, attempt_number)
        result: InferenceResult | None = None
        try:
            check()
            # Recheck current policy/credentials immediately before dispatch.
            fresh = self.authority.stage(
                context,
                call.trace.policy,
                call.trace.node_id,
                alias=call.trace.alias_id,
                data_class=authorized.data_class,
                configuration_id=authorized.stage.configuration_id,
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
            validate_completion(request, result.completion)
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
                    context,
                    attempt,
                    result,
                    cancelled=isinstance(error, asyncio.CancelledError),
                    failed=True,
                )
            if isinstance(error, asyncio.CancelledError):
                raise
            raise DomainError(
                ErrorCode.UNSUPPORTED, "Inference failed; inspect pending accounting", 503
            ) from None

    async def infer(
        self,
        context: RequestContext,
        authorized: AuthorizedStage,
        request: ChatCompletionRequest,
        run_id: str,
    ) -> tuple[InferenceResult, RunAttempt]:
        last: DomainError | None = None
        for index, candidate in enumerate(self.candidates(context, authorized, request)):
            # Nonstream output is not exposed until validation/accounting completes.
            attempt_context = (
                context
                if index == 0
                else replace(context, request_id=fingerprint(context.request_id, index)[:32])
            )
            try:
                return await self._infer_once(
                    attempt_context, candidate, request, run_id, index + 1
                )
            except DomainError as error:
                last = error
                context.check_cancelled()
        assert last is not None
        raise last

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
    ) -> AsyncGenerator[ChatCompletionChunk | GatewayError, None]:
        from ..execution_contracts import ChunkChoice, CompletionDelta
        from ..stream_validation import StreamCollector

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
        candidates = self.candidates(context, authorized, outgoing)
        for index, candidate in enumerate(candidates):
            child = (
                context
                if index == 0
                else replace(context, request_id=fingerprint(context.request_id, index)[:32])
            )
            attempt = None
            exposed = False
            collector = StreamCollector()
            observation: StreamObservation | None = None
            try:
                self.keys.check(context, "chat:complete", alias=value.model)
                call, attempt = self.start(
                    child, candidate, outgoing, context.request_id, index + 1
                )
                fresh = self.authority.stage(
                    child,
                    call.trace.policy,
                    call.trace.node_id,
                    alias=value.model,
                    configuration_id=candidate.stage.configuration_id,
                )
                if fresh.target != candidate.target or fresh.credential != candidate.credential:
                    raise ValueError("Endpoint changed before stream")
                self.store.save_attempt(
                    child.tenant_id, attempt.model_copy(update={"status": "dispatched"}), 2
                )
                async with asyncio.timeout(
                    min(
                        candidate.stage.budget.timeout_ms / 1000,
                        max(0, (context.deadline - datetime.now(UTC)).total_seconds()),
                    )
                ):
                    async for event in self.inference.stream(child, call):
                        context.check_cancelled()
                        self.keys.check(context, "chat:complete", alias=value.model)
                        self.authority.policy(context, call.trace.policy)
                        if isinstance(event, GatewayError):
                            raise ValueError("Upstream stream error")
                        if isinstance(event, StreamObservation):
                            if observation is not None:
                                raise ValueError("Duplicate terminal accounting")
                            observation = event
                            continue
                        if observation is not None or event.model != value.model:
                            raise ValueError("Data after terminal observation or alias mismatch")
                        collector.accept(event)
                        if not event.choices:
                            # Usage-only chunks are retained, then exposed with terminal accounting.
                            continue
                        choice = event.choices[0]
                        if (
                            choice.delta.content is not None
                            or choice.delta.tool_calls
                            or choice.delta.role
                        ):
                            exposed = True
                            yield event.model_copy(
                                update={
                                    "choices": (choice.model_copy(update={"finish_reason": None}),)
                                }
                            )
                    completion = collector.completion(child.request_id, value.model)
                    validate_completion(outgoing, completion)
                    result = InferenceResult(
                        completion,
                        observation.actual_micro_usd if observation else None,
                        observation.usage if observation else collector.usage,
                        observation.trace if observation else call.trace,
                    )
                    if result.usage and result.usage.completion_tokens > outgoing.max_tokens:
                        raise ValueError("Output token ceiling exceeded")
                    done = self.finish(child, attempt, result)
                    if done.error:
                        raise ValueError("Accounting ceiling exceeded")
                    self.store.advance_request(
                        context.tenant_id,
                        context.request_id,
                        "running",
                        "succeeded" if done.usage.actual_micro_usd is not None else "uncertain",
                    )
                    yield ChatCompletionChunk(
                        id=child.request_id,
                        created=completion.created,
                        model=value.model,
                        choices=(
                            ChunkChoice(
                                delta=CompletionDelta(),
                                finish_reason=completion.choices[0].finish_reason,
                            ),
                        ),
                        usage=result.usage,
                    )
                    return
            except (GeneratorExit, asyncio.CancelledError, Exception) as error:
                if attempt:
                    try:
                        self.store.trace(child.tenant_id, child.request_id)
                    except DomainError:
                        self.finish(child, attempt, None, partial=exposed)
                interrupted = isinstance(error, (GeneratorExit, asyncio.CancelledError))
                if exposed or interrupted or index + 1 == len(candidates):
                    if self.store.request_state(context.tenant_id, context.request_id) == "running":
                        self.store.advance_request(
                            context.tenant_id, context.request_id, "running", "uncertain"
                        )
                    if interrupted:
                        raise
                    yield failure(partial=exposed)
                    return
                # All preceding attempts are accounted; no downstream response yet.
                context.check_cancelled()
