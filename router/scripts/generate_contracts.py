"""Deterministic generated artifacts, no startup, storage or network operations."""

import json
from pathlib import Path

from buildbox_router.api import create_app
from buildbox_router.contracts import ExecutionTool, ResearchTool
from pydantic import TypeAdapter

root = Path(__file__).resolve().parents[1]
schema = create_app().openapi()
# Distinct tool registries are contract-only until live integration is approved.
for model in (ResearchTool, ExecutionTool):
    schema["components"]["schemas"][model.__name__] = TypeAdapter(model).json_schema()
(root / "openapi.json").write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
