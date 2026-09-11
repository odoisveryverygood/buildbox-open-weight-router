"""Bounded typed reconstruction for terminal validation, never tool execution."""

from .execution_contracts import (
    ChatCompletion,
    ChatCompletionChunk,
    CompletionMessage,
    CompletionUsage,
    FunctionCall,
    ToolCall,
)


class StreamCollector:
    def __init__(self) -> None:
        self.text = ""
        self.calls: dict[int, ToolCall] = {}
        self.usage: CompletionUsage | None = None
        self.finish: str | None = None

    def accept(self, chunk: ChatCompletionChunk) -> None:
        if chunk.usage:
            if self.usage is not None and self.usage != chunk.usage:
                raise ValueError("Conflicting usage events")
            self.usage = chunk.usage
        for choice in chunk.choices:
            delta = choice.delta
            if self.finish and (delta.content or delta.tool_calls):
                raise ValueError("Output after finish reason")
            if choice.finish_reason:
                if self.finish and choice.finish_reason != self.finish:
                    raise ValueError("Conflicting finish reason")
                self.finish = choice.finish_reason
            self.text += delta.content or ""
            for part in delta.tool_calls or ():
                previous = self.calls.get(part.index)
                if previous is None:
                    if not part.id or not part.function or not part.function.name:
                        raise ValueError("First tool delta must identify its call")
                    previous = ToolCall(
                        id=part.id, function=FunctionCall(name=part.function.name, arguments="")
                    )
                elif (part.id is not None and part.id != previous.id) or (
                    part.function
                    and part.function.name
                    and part.function.name != previous.function.name
                ):
                    raise ValueError("Tool delta identity changed")
                arguments = previous.function.arguments + (
                    part.function.arguments or "" if part.function else ""
                )
                self.calls[part.index] = ToolCall(
                    id=previous.id,
                    function=FunctionCall(name=previous.function.name, arguments=arguments),
                )
            if (
                len(self.text.encode())
                + sum(len(c.function.arguments.encode()) for c in self.calls.values())
                > 1048576
            ):
                raise ValueError("Stream reconstruction exceeds bound")

    def completion(self, request_id: str, alias: str) -> ChatCompletion:
        if self.finish is None:
            raise ValueError("Missing stream finish reason")
        return ChatCompletion.model_validate(
            {
                "id": request_id,
                "model": alias,
                "created": 0,
                "choices": [
                    {
                        "index": 0,
                        "message": CompletionMessage(
                            content=self.text or None,
                            tool_calls=tuple(self.calls[k] for k in sorted(self.calls)) or None,
                        ),
                        "finish_reason": self.finish,
                    }
                ],
                "usage": self.usage,
            }
        )
