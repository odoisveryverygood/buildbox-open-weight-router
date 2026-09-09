"""Typed provider wire codecs. Provider extensions do not change gateway authority."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .execution_contracts import (
    ChatMessage,
    CompletionDelta,
    CompletionMessage,
    CompletionUsage,
    NamedToolChoice,
    ResponseFormat,
    ToolDefinition,
)


class ProviderControls(BaseModel):
    only: tuple[str, ...]
    order: tuple[str, ...]
    allow_fallbacks: Literal[False] = False
    require_parameters: Literal[True] = True
    data_collection: Literal["deny"] = "deny"
    zdr: Literal[True] = True
    max_price: dict[Literal["prompt", "completion"], float]


class ProviderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True, serialize_by_alias=True)
    model: str
    messages: tuple[ChatMessage, ...]
    max_tokens: int
    temperature: float | None = None
    stream: bool = False
    tools: tuple[ToolDefinition, ...] | None = None
    tool_choice: Literal["auto", "none", "required"] | NamedToolChoice | None = None
    response_format: ResponseFormat | None = None
    provider: ProviderControls | None = None


class UpstreamError(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    code: str | int | None = None
    message: str = Field(default="Upstream error", repr=False)


class ProviderUsage(CompletionUsage):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ProviderMessage(CompletionMessage):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    refusal: str | None = Field(default=None, repr=False)


class ProviderDelta(CompletionDelta):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    refusal: str | None = Field(default=None, repr=False)


class ProviderChoice(BaseModel):
    # Additional upstream metadata (e.g. native_finish_reason) is not a caller
    # requirement. Never copy provider reasoning fields into logs or wire output.
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    index: Literal[0] = 0
    message: ProviderMessage | None = None
    delta: ProviderDelta | None = None
    finish_reason: Literal["stop", "length", "content_filter", "tool_calls", "error"] | None = None


class ProviderFrame(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    id: str | None = None
    model: str | None = None
    created: int = Field(default=0, ge=0)
    provider: str | None = None
    choices: tuple[ProviderChoice, ...] = Field(default=(), max_length=1)
    usage: ProviderUsage | None = None
    error: UpstreamError | None = None
