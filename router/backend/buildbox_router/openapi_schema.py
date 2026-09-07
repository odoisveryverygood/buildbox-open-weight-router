"""Central contract-only schema generation; no live composition or database IO."""

from typing import Any

from pydantic import TypeAdapter

from .contracts import ExecutionTool, ResearchTool
from .execution_contracts import ExecutionSchemaBundle


def enrich_schema(schema: dict[str, Any]) -> dict[str, Any]:
    for model in (ResearchTool, ExecutionTool, ExecutionSchemaBundle):
        value = TypeAdapter(model).json_schema(ref_template="#/components/schemas/{model}")
        schema["components"]["schemas"].update(value.pop("$defs", {}))
        schema["components"]["schemas"][model.__name__] = value
    schema["components"].setdefault("securitySchemes", {})["SandboxApplicationKey"] = {
        "type": "http",
        "scheme": "bearer",
        "description": "Tenant application key with scopes and exact alias/policy allowlist; not an upstream provider key.",
    }
    for path, operations in schema["paths"].items():
        if path.startswith("/v1/"):
            for operation in operations.values():
                operation["security"] = [{"SandboxApplicationKey": []}]
    return schema


def canonical_openapi() -> dict[str, Any]:
    from .api import create_app

    return create_app().openapi()
