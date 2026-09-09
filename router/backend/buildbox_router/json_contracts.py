"""Canonical deliberately bounded JSON Schema subset, shared by chat and tools."""

import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class JsonSchema(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
        hide_input_in_errors=True,
    )
    type: Literal["object", "array", "string", "number", "integer", "boolean", "null"]
    description: str | None = Field(default=None, max_length=1000)
    properties: dict[str, "JsonSchema"] | None = None
    required: tuple[str, ...] = ()
    additional_properties: Literal[False] | None = Field(default=None, alias="additionalProperties")
    items: "JsonSchema | None" = None
    enum: tuple[JsonValue, ...] | None = None

    @model_validator(mode="after")
    def supported(self) -> "JsonSchema":
        json.dumps(self.enum, allow_nan=False)
        if self.type == "object":
            if (
                self.properties is None
                or self.additional_properties is not False
                or set(self.required) != set(self.properties)
            ):
                raise ValueError("Strict objects require all declared properties and forbid extras")
        elif self.properties is not None or self.required or self.additional_properties is not None:
            raise ValueError("Object keywords require object type")
        if (self.type == "array") != (self.items is not None):
            raise ValueError("Array schemas require items only")
        if len(self.model_dump_json()) > 16000:
            raise ValueError("Schema exceeds supported size")
        return self

    def validate_value(self, value: JsonValue, depth: int = 0) -> None:
        if depth > 20:
            raise ValueError("JSON nesting exceeds limit")
        valid = {
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "number": type(value) in (float, int),
            "integer": type(value) is int,
            "boolean": type(value) is bool,
            "null": value is None,
        }[self.type]
        if not valid or (
            self.enum is not None
            and not any(type(v) is type(value) and v == value for v in self.enum)
        ):
            raise ValueError("Output does not satisfy JSON schema")
        if isinstance(value, dict):
            if set(value) != set(self.properties or {}):
                raise ValueError("JSON properties mismatch")
            for key, schema in (self.properties or {}).items():
                schema.validate_value(value[key], depth + 1)
        if isinstance(value, list) and self.items:
            if len(value) > 10000:
                raise ValueError("JSON array exceeds limit")
            for item in value:
                self.items.validate_value(item, depth + 1)


def parse_json(value: str) -> JsonValue:
    def invalid(_: str) -> None:
        raise ValueError("Non-finite JSON number")

    def pairs(items: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        if len(dict(items)) != len(items):
            raise ValueError("Duplicate JSON keys")
        return dict(items)

    def finite(raw: str) -> float:
        result = float(raw)
        if not math.isfinite(result):
            raise ValueError("Non-finite JSON number")
        return result

    result: JsonValue = json.loads(
        value, parse_constant=invalid, parse_float=finite, object_pairs_hook=pairs
    )
    return result
