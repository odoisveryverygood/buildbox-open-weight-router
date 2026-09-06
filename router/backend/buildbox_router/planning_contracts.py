"""Canonical planning API v1.1 composing unchanged v1 workflow/catalog records."""

from typing import Literal

from pydantic import Field, model_validator

from .contracts import (
    CatalogSnapshot,
    Contract,
    Identifier,
    Intake,
    Interpretation,
    Job,
    Recommendation,
    Workflow,
)
from .evidence_contracts import ResearchLedger


class ProcessingPolicy(Contract):
    inference: Literal["local_only", "local_model", "approved_hosted"] = "local_only"
    public_research: bool = False
    interpretation_role: Identifier = "interpretation"
    research_role: Identifier = "research"
    max_planning_usd: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)


class TargetRequirements(Contract):
    input_modality: Literal["text", "image"] = "text"
    deployment: Literal["any", "self_hosted"] = "any"
    structured_output: bool = False
    tool_calling: bool = False


class ClarificationAnswer(Contract):
    question_id: str = Field(min_length=1, max_length=200)
    answer: str = Field(min_length=1, max_length=2000)


class PlanInput(Contract):
    intake: Intake
    processing: ProcessingPolicy = Field(default_factory=ProcessingPolicy)
    requirements: TargetRequirements = Field(default_factory=TargetRequirements)
    answers: tuple[ClarificationAnswer, ...] = Field(default=(), max_length=30)
    edited_workflow: Workflow | None = None
    catalog_mode: Literal["fixture", "public_snapshot", "runtime_public"] = "fixture"


class PlanVersion(Contract):
    id: Identifier
    version: int = Field(ge=1)
    input: PlanInput
    input_hash: str
    planning_schema: Literal["1.1"] = "1.1"


class PlanningResult(Contract):
    plan_id: Identifier
    version: int
    interpretation: Interpretation
    workflow: Workflow | None = None
    catalog: CatalogSnapshot | None = None
    research: ResearchLedger | None = None
    recommendation: Recommendation | None = None
    status: Literal["needs_clarification", "blocked", "provisional", "deterministic"]
    exclusions: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    assumptions: tuple[str, ...] = ()
    missing_facts: tuple[str, ...] = ()
    evaluation_status: Literal["not_run"] = "not_run"
    fixture: bool
    planning_schema: Literal["1.1"] = "1.1"

    @model_validator(mode="after")
    def exact_versions(self) -> "PlanningResult":
        if self.workflow and (self.workflow.id, self.workflow.version) != (
            self.plan_id,
            self.version,
        ):
            raise ValueError("Workflow result version mismatch")
        if self.recommendation and (
            self.recommendation.workflow_id,
            self.recommendation.workflow_version,
        ) != (self.plan_id, self.version):
            raise ValueError("Recommendation result version mismatch")
        return self


class PlanView(Contract):
    plan: PlanVersion
    latest_version: int
    stale: bool
    job: Job
    result: PlanningResult | None = None
    planning_schema: Literal["1.1"] = "1.1"


class PlanningCapabilities(Contract):
    mode: Literal["fixture", "live"]
    authentication: Literal["local_fixture", "shared"]
    interpretation_available: bool
    public_runtime_available: bool = True
    local_model: str | None = None
    evaluation_status: Literal["not_run"] = "not_run"
    live_gate: str
