"""Target adapters reuse shared guarded transports; no live clients on import.

Shared approved-target transport yields incremental network bytes. Buffered JSON
completion is never represented as live token streaming.
"""

import asyncio
import re
from collections.abc import AsyncIterator, Callable, Iterator
from decimal import ROUND_CEILING, Decimal, InvalidOperation

from pydantic import JsonValue

from ..contracts import ErrorCode, Fact, Provenance
from ..errors import DomainError
from ..execution_contracts import (
    ApprovedEndpoint,
    ChatCompletion,
    ChatCompletionChunk,
    ChunkChoice,
    CompletionChoice,
    CompletionDelta,
    CompletionMessage,
    CompletionUsage,
    GatewayError,
    StreamObservation,
)
from ..execution_ports import InferenceCall, InferenceResult, RequestContext
from ..inference_transport import exchange
from ..json_contracts import parse_json
from ..local_inference import local_request
from ..provider_contracts import ProviderControls, ProviderFrame, ProviderRequest
from ..runtime import guarded_request


def identity(value: object, request_id: str) -> Fact[str]:
    if (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_./: -]{1,200}", value)
        and not re.search(r"sk-|bearer|password|key|token|@", value, re.I)
    ):
        return Fact[str](
            value=value,
            provenance=Provenance(
                kind="observed",
                source="Provider response metadata, not independently verified weights",
                evidence_ids=(request_id,),
            ),
        )
    return Fact[str](
        unknown_reason="Served identity not safely observable",
        provenance=Provenance(kind="inference", source="Provider response identity absent"),
    )


def usage(value: object) -> CompletionUsage | None:
    if not isinstance(value, dict) or not all(
        k in value for k in ("prompt_tokens", "completion_tokens", "total_tokens")
    ):
        return None
    return CompletionUsage.model_validate(
        {k: value[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    )


def actual_cost(value: object) -> int | None:
    if (
        not isinstance(value, dict)
        or isinstance(value.get("cost"), bool)
        or value.get("cost") is None
    ):
        return None
    try:
        amount = Decimal(str(value["cost"]))
        if not amount.is_finite() or amount < 0:
            return None
        return int((amount * 1000000).to_integral_value(rounding=ROUND_CEILING))
    except InvalidOperation:
        return None


class TargetAdapters:
    def __init__(
        self,
        secret: Callable[[str, str], str],
        endpoints: Callable[[str, str], ApprovedEndpoint] | None = None,
    ) -> None:
        self.secret = secret  # Operator-injected secret manager, not environment discovery.
        self.endpoints = endpoints

    async def complete(self, context: RequestContext, call: InferenceCall) -> InferenceResult:
        context.check_cancelled()
        try:
            if call.target.local:
                return await asyncio.to_thread(self._local, context, call)
            if call.target.approved_endpoint_id:
                raw = b""
                async for part in self._exchange(context, call, False):
                    raw += part
                return self._result(context, call, ProviderFrame.model_validate_json(raw))
            return await asyncio.to_thread(self._hosted, context, call)
        except asyncio.CancelledError:
            raise
        except Exception:
            raise DomainError(
                ErrorCode.UNSUPPORTED, "Target inference failed; usage may remain pending", 503
            ) from None

    def _hosted(self, context: RequestContext, call: InferenceCall) -> InferenceResult:
        endpoint = call.target.endpoint
        if (
            not endpoint
            or call.credential.adapter_id != "openrouter"
            or not call.credential.secret_reference
        ):
            raise ValueError("Hosted credential missing")
        payload = self._request(call, False).model_dump(mode="json", exclude_none=True)
        response = guarded_request(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=payload,
            key=self.secret(context.tenant_id, call.credential.secret_reference),
            check=context.check_cancelled,
        )
        return self._result(context, call, ProviderFrame.model_validate(response))

    def _result(
        self, context: RequestContext, call: InferenceCall, frame: ProviderFrame
    ) -> InferenceResult:
        endpoint = call.target.endpoint
        if not endpoint or frame.error or frame.model != endpoint.routing_model_id:
            raise ValueError("Upstream error or model identity mismatch")
        if len(frame.choices) != 1:
            raise ValueError("Invalid upstream choices")
        choice = frame.choices[0]
        if (
            choice.message is None
            or choice.message.refusal
            or choice.finish_reason in (None, "error")
        ):
            raise ValueError("Invalid upstream completion")
        assert choice.finish_reason is not None and choice.finish_reason != "error"
        observed = usage(frame.usage.model_dump() if frame.usage else None)
        result = ChatCompletion(
            id=context.request_id,
            created=frame.created,
            model=call.messages.model,
            choices=(
                CompletionChoice(
                    message=CompletionMessage(
                        content=choice.message.content, tool_calls=choice.message.tool_calls
                    ),
                    finish_reason=choice.finish_reason,
                ),
            ),
            usage=observed,
        )
        trace = call.trace.model_copy(
            update={
                "served_model": identity(frame.model, context.request_id),
                "served_endpoint": identity(frame.provider, context.request_id),
            }
        )
        # Provider name is recorded, not misrepresented as exact endpoint/revision proof.
        return InferenceResult(
            result,
            actual_cost(frame.usage.model_dump() if frame.usage else None),
            result.usage,
            trace,
        )

    def _request(self, call: InferenceCall, stream: bool) -> ProviderRequest:
        endpoint = call.target.endpoint
        if not endpoint:
            raise ValueError("OpenAI-compatible deployment required")
        controls = None
        if call.credential.adapter_id == "openrouter":
            controls = ProviderControls(
                only=(endpoint.endpoint_tag,),
                order=(endpoint.endpoint_tag,),
                max_price={
                    "prompt": next(
                        float(p.usd_per_million_tokens or "0")
                        for p in endpoint.prices
                        if p.component == "prompt"
                    ),
                    "completion": next(
                        float(p.usd_per_million_tokens or "0")
                        for p in endpoint.prices
                        if p.component == "completion"
                    ),
                },
            )
        return ProviderRequest(
            model=endpoint.routing_model_id,
            messages=call.messages.messages,
            max_tokens=call.messages.max_tokens,
            temperature=call.messages.temperature,
            stream=stream,
            tools=call.messages.tools,
            tool_choice=call.messages.tool_choice,
            response_format=call.messages.response_format,
            provider=controls,
        )

    async def _exchange(
        self, context: RequestContext, call: InferenceCall, stream: bool
    ) -> AsyncIterator[bytes]:
        if call.target.approved_endpoint_id:
            if self.endpoints is None:
                raise ValueError("No approved endpoint registry")
            endpoint = self.endpoints(context.tenant_id, call.target.approved_endpoint_id)
            if (
                endpoint.id != call.target.approved_endpoint_id
                or endpoint.adapter_id != call.credential.adapter_id
            ):
                raise ValueError("Approved endpoint pin mismatch")
        else:
            endpoint = ApprovedEndpoint(
                id="openrouter",
                tenant_id=context.tenant_id,
                url="https://openrouter.ai/api/v1/chat/completions",
                network="public_https",
                adapter_id="openrouter",
                credential_reference_id=call.credential.id,
                expires_at=call.credential.expires_at,
                authorization_reference=call.credential.approval_reference,
            )
        if (
            endpoint.tenant_id != context.tenant_id
            or endpoint.credential_reference_id != call.credential.id
        ):
            raise ValueError("Endpoint workspace/credential mismatch")
        key = (
            self.secret(context.tenant_id, call.credential.secret_reference)
            if call.credential.secret_reference
            else None
        )
        async for part in exchange(
            endpoint,
            self._request(call, stream),
            key,
            context.check_cancelled,
            call.budget.timeout_ms / 1000,
        ):
            yield part

    def _local(self, context: RequestContext, call: InferenceCall) -> InferenceResult:
        local = call.target.local
        if (
            not local
            or call.credential.adapter_id != "local_ollama"
            or "cloud" in local.model_tag.lower()
        ):
            raise ValueError("Local deployment denied")
        tags = local_request("/api/tags", None, context.check_cancelled)
        entries = tags.get("models")
        matches = (
            [v for v in entries if isinstance(v, dict) and v.get("name") == local.model_tag]
            if isinstance(entries, list)
            else []
        )
        if len(matches) != 1 or matches[0].get("digest") != local.weights_digest.value:
            raise ValueError("Cached weights digest mismatch; no pull permitted")
        options: dict[str, object] = {
            "num_predict": call.messages.max_tokens,
            "num_ctx": local.context_tokens.value,
        }
        if call.messages.temperature is not None:
            options["temperature"] = call.messages.temperature
        response = local_request(
            "/api/chat",
            {
                "model": local.model_tag,
                "stream": False,
                "keep_alive": 0,
                "messages": [m.model_dump() for m in call.messages.messages],
                "options": options,
            },
            context.check_cancelled,
        )
        if (
            response.get("model") != local.model_tag
            or response.get("done") is not True
            or response.get("error")
        ):
            raise ValueError("Local model incomplete or identity mismatch")
        message = response.get("message")
        if not isinstance(message, dict) or message.get("tool_calls"):
            raise ValueError("Local output unsupported")
        observed = None
        counts = response.get("prompt_eval_count"), response.get("eval_count")
        if all(type(x) is int and x >= 0 for x in counts):
            observed = CompletionUsage(
                prompt_tokens=int(str(counts[0])),
                completion_tokens=int(str(counts[1])),
                total_tokens=sum(int(str(x)) for x in counts),
            )
        completion = ChatCompletion.model_validate(
            {
                "id": context.request_id,
                "created": 0,
                "model": call.messages.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": message.get("content")},
                        "finish_reason": response.get("done_reason"),
                    }
                ],
                "usage": observed,
            }
        )
        return InferenceResult(
            completion,
            0,
            observed,
            call.trace.model_copy(
                update={
                    "served_model": identity(local.model_tag, context.request_id),
                    "served_endpoint": identity("ollama-loopback-11444", context.request_id),
                }
            ),
        )

    async def stream(
        self, context: RequestContext, call: InferenceCall
    ) -> AsyncIterator[ChatCompletionChunk | GatewayError | StreamObservation]:
        decoder = SSEDecoder()
        observed = None
        actual = None
        trace = call.trace
        terminal = False
        async for block in self._exchange(context, call, True):
            for event in decoder.iter_feed(block):
                if event == "[DONE]":
                    continue
                frame = ProviderFrame.model_validate(event)
                if frame.error or (
                    frame.model is not None
                    and call.target.endpoint
                    and frame.model != call.target.endpoint.routing_model_id
                ):
                    raise ValueError("Upstream stream error/model mismatch")
                if frame.model:
                    trace = trace.model_copy(
                        update={"served_model": identity(frame.model, context.request_id)}
                    )
                if frame.provider:
                    trace = trace.model_copy(
                        update={"served_endpoint": identity(frame.provider, context.request_id)}
                    )
                if frame.usage:
                    observed = usage(frame.usage.model_dump())
                    actual = actual_cost(frame.usage.model_dump())
                choices = []
                for choice in frame.choices:
                    if choice.finish_reason == "error" or (choice.delta and choice.delta.refusal):
                        raise ValueError("Upstream terminal error")
                    terminal = terminal or choice.finish_reason is not None
                    choices.append(
                        ChunkChoice(
                            index=choice.index,
                            delta=CompletionDelta(
                                content=choice.delta.content,
                                role=choice.delta.role,
                                tool_calls=choice.delta.tool_calls,
                            )
                            if choice.delta
                            else CompletionDelta(),
                            finish_reason=choice.finish_reason,
                        )
                    )
                yield ChatCompletionChunk(
                    id=context.request_id,
                    created=frame.created,
                    model=call.messages.model,
                    choices=tuple(choices),
                    usage=observed if frame.usage else None,
                )
        decoder.finish()
        if not terminal:
            raise ValueError("Upstream stream lacks finish reason")
        yield StreamObservation(usage=observed, actual_micro_usd=actual, trace=trace)


class SSEDecoder:
    """Bounded incremental UTF-8/SSE decoder. Does not open a connection."""

    def __init__(self) -> None:
        self.buffer = b""
        self.data: list[str] = []
        self.size = 0
        self.done = False

    def feed(self, chunk: bytes) -> list[dict[str, JsonValue] | str]:
        return list(self.iter_feed(chunk))

    def iter_feed(self, chunk: bytes) -> Iterator[dict[str, JsonValue] | str]:
        self.size += len(chunk)
        if self.size > 1048576:
            raise ValueError("Stream exceeds total bound")
        self.buffer += chunk
        while b"\n" in self.buffer:
            raw, self.buffer = self.buffer.split(b"\n", 1)
            line = raw.rstrip(b"\r").decode("utf-8", errors="strict")
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                self.data.append(line[5:].removeprefix(" "))
            elif not line and self.data:
                payload = "\n".join(self.data)
                self.data = []
                if self.done:
                    raise ValueError("Data after terminal event")
                if payload == "[DONE]":
                    self.done = True
                    yield payload
                else:
                    value = parse_json(payload)
                    if not isinstance(value, dict) or "error" in value:
                        raise ValueError("Upstream stream error")
                    yield value
        if len(self.buffer) > 65536:
            raise ValueError("Stream frame exceeds bound")

    def finish(self) -> None:
        if self.buffer.strip() or self.data or not self.done:
            raise ValueError("Truncated stream or missing terminal event")
