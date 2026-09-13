"""Presentation metadata for explicit local demos; never execution authority."""

from pydantic import JsonValue

from .contracts import CatalogSnapshot, Fact
from .execution_contracts import ExecutionContract, ToolDefinition, VersionRef


class DemoScenario(ExecutionContract):
    id: str
    title: str
    task: str
    requirements: tuple[str, ...]
    policy: VersionRef
    plan: VersionRef
    alias: str
    admission_id: str
    selected: str
    alternative: VersionRef | None = None
    alternative_admission: str | None = None
    explanation: str
    assessments: dict[str, tuple[Fact[bool], ...]]
    inputs: dict[str, JsonValue]
    expected: JsonValue
    tools: tuple[ToolDefinition, ...] = ()


class DemoManifest(ExecutionContract):
    mode: str = "synthetic_upstream"
    catalog: CatalogSnapshot
    scenarios: tuple[DemoScenario, ...]
    fallback: DemoScenario
