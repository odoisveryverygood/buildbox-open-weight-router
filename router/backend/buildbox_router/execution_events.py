"""Shared SSE encoding only; formatting an event does not claim execution."""

from .execution_contracts import ChatCompletionChunk, GatewayError, RunEvent


def chat_sse(value: ChatCompletionChunk | GatewayError) -> str:
    return "data: " + value.model_dump_json(exclude_none=True) + "\n\n"


def run_sse(value: RunEvent) -> str:
    return f"id: {value.sequence}\nevent: {value.type}\ndata: {value.model_dump_json(exclude_none=True)}\n\n"


CHAT_DONE = "data: [DONE]\n\n"
