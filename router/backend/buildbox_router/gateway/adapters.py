"""Target adapters reuse shared guarded transports; no live clients on import.

Network streaming is intentionally unavailable until the shared transport port
can yield bytes. Never turn a buffered completion into fake token streaming.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from typing import Any

from ..contracts import ErrorCode, Fact, Provenance
from ..errors import DomainError
from ..execution_contracts import ChatCompletion, ChatCompletionChunk, CompletionUsage, GatewayError
from ..execution_ports import InferenceCall, InferenceResult, RequestContext
from ..local_inference import local_request
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
    def __init__(self, secret: Callable[[str, str], str]) -> None:
        self.secret = secret  # Operator-injected secret manager, not environment discovery.

    async def complete(self, context: RequestContext, call: InferenceCall) -> InferenceResult:
        context.check_cancelled()
        try:
            if call.target.local:
                return await asyncio.to_thread(self._local, context, call)
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
        # Fixed guarded destination. Ignore metadata serving_url; never route to user URLs.
        payload: dict[str, object] = {
            "model": endpoint.routing_model_id,
            "stream": False,
            "messages": [m.model_dump() for m in call.messages.messages],
            "max_tokens": call.messages.max_tokens,
            "provider": {
                "only": [endpoint.endpoint_tag],
                "order": [endpoint.endpoint_tag],
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
                "zdr": True,
                "max_price": {
                    p.component: float(p.usd_per_million_tokens or "0")
                    for p in endpoint.prices
                    if p.component in ("prompt", "completion")
                },
            },
        }
        if call.messages.temperature is not None:
            payload["temperature"] = call.messages.temperature
        response = guarded_request(
            "https://openrouter.ai/api/v1/chat/completions",
            payload=payload,
            key=self.secret(context.tenant_id, call.credential.secret_reference),
            check=context.check_cancelled,
        )
        if "error" in response or response.get("model") != endpoint.routing_model_id:
            raise ValueError("Upstream error or model identity mismatch")
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError("Invalid upstream choices")
        choice = choices[0]
        message = choice.get("message")
        if (
            not isinstance(message, dict)
            or message.get("tool_calls")
            or message.get("function_call")
        ):
            raise ValueError("Unexpected tool output is not supported")
        result = ChatCompletion.model_validate(
            {
                "id": context.request_id,
                "created": response.get("created", 0),
                "model": call.messages.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": message.get("content")},
                        "finish_reason": choice.get("finish_reason"),
                    }
                ],
                "usage": usage(response.get("usage")),
            }
        )
        trace = call.trace.model_copy(
            update={
                "served_model": identity(response.get("model"), context.request_id),
                "served_endpoint": identity(response.get("provider"), context.request_id),
            }
        )
        # Provider name is recorded, not misrepresented as exact endpoint/revision proof.
        return InferenceResult(result, actual_cost(response.get("usage")), result.usage, trace)

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
    ) -> AsyncIterator[ChatCompletionChunk | GatewayError]:
        raise DomainError(
            ErrorCode.UNSUPPORTED,
            "Shared guarded byte-stream transport not available; no upstream call",
            503,
        )
        yield  # pragma: no cover


class SSEDecoder:
    """Bounded incremental UTF-8/SSE decoder. Does not open a connection."""

    def __init__(self) -> None:
        self.buffer = b""
        self.data: list[str] = []
        self.size = 0
        self.done = False

    def feed(self, chunk: bytes) -> list[dict[str, Any] | str]:
        self.size += len(chunk)
        if self.size > 1048576:
            raise ValueError("Stream exceeds total bound")
        self.buffer += chunk
        result: list[dict[str, Any] | str] = []
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
                    result.append(payload)
                else:
                    value = json.loads(payload)
                    if not isinstance(value, dict) or "error" in value:
                        raise ValueError("Upstream stream error")
                    result.append(value)
        if len(self.buffer) > 65536:
            raise ValueError("Stream frame exceeds bound")
        return result

    def finish(self) -> None:
        if self.buffer.strip() or self.data or not self.done:
            raise ValueError("Truncated stream or missing terminal event")
