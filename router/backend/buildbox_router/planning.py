"""Central composition of the two verified lanes. Plans never execute workflows."""

import hashlib
import json
import re
from importlib.resources import files

from .config import Settings
from .contracts import (
    CatalogSnapshot,
    Constraints,
    ErrorCode,
    Example,
    Intake,
    Interpretation,
    Job,
    Node,
    Provenance,
    Workflow,
    WorkflowTool,
)
from .errors import DomainError
from .evidence_contracts import SourceCapture
from .intelligence.selection.engine import DeterministicSelector
from .intelligence.workflow.interpreter import (
    RecordedInference,
    SchemaInterpreter,
    deterministic_workflow,
)
from .local_inference import interpret_local
from .planning_contracts import PlanningResult, PlanVersion
from .planning_storage import PlanningStorage
from .research.fixture import SyntheticCatalog
from .research.jobs import ArtifactInput, ResearchPlan
from .research.service import PublicResearch
from .research.sources import RecordedSources
from .runtime import PUBLIC_REPOSITORY, OpenRouterRole, approval_for, public_sources
from .storage import SqlStorage
from .workflow_proposal import single_stage, unresolved


def planning_examples() -> list[Example]:
    descriptions = (
        (
            "extraction",
            "Document extraction",
            "Normalize input documents, extract fields, and ask a human to review the output.",
            (),
        ),
        (
            "support",
            "Support and tool workflow",
            "Classify support tickets, retrieve context with the declared knowledge tool, draft an answer, then ask a human to review.",
            (
                WorkflowTool(
                    id="knowledge", description="Declared read-only knowledge lookup; not connected"
                ),
            ),
        ),
        (
            "company-research",
            "Company research",
            "Research a company from public input documents using the declared public_search tool. Summarize evidence with a bounded agent: max_iterations=2, max_model_calls=3; stop when sources are exhausted. Ask a human to review the output.",
            (
                WorkflowTool(
                    id="public_search",
                    description="Declared public search for target workflow; not connected",
                ),
            ),
        ),
    )
    return [
        Example(
            id=i,
            title=title,
            intake=Intake(
                example_id=i,
                description=description,
                tools=tools,
                constraints=Constraints(
                    max_cost_per_1k_tokens=1.0,
                    required_region="local",
                    provenance=Provenance(
                        kind="synthetic", source="Explicit synthetic planning example"
                    ),
                ),
            ),
        )
        for i, title, description, tools in descriptions
    ]


def example_workflow(intake: Intake, identifier: str) -> Workflow | None:
    example = next((e for e in planning_examples() if e.id == intake.example_id), None)
    if (
        example is None
        or intake.description != example.intake.description
        or intake.tools != example.intake.tools
    ):
        return None
    nodes: tuple[Node, ...]
    if example.id == "extraction":
        nodes = (
            Node(id="normalize", kind="code", purpose="Normalize documents"),
            Node(id="extract", kind="llm", purpose="Extract fields", depends_on=("normalize",)),
            Node(
                id="review", kind="human_approval", purpose="Review output", depends_on=("extract",)
            ),
        )
    elif example.id == "support":
        nodes = (
            Node(id="classify", kind="llm", purpose="Classify tickets"),
            Node(
                id="lookup",
                kind="tool",
                purpose="Read knowledge",
                tool_id="knowledge",
                depends_on=("classify",),
            ),
            Node(
                id="answer", kind="llm", purpose="Draft answer from context", depends_on=("lookup",)
            ),
            Node(
                id="review", kind="human_approval", purpose="Review answer", depends_on=("answer",)
            ),
        )
    else:
        nodes = (
            Node(
                id="research",
                kind="bounded_agent",
                purpose="Summarize supplied public documents; stop when sources exhausted",
                allowed_tools=("public_search",),
                max_iterations=2,
                max_model_calls=3,
            ),
            Node(
                id="review",
                kind="human_approval",
                purpose="Review cited summary",
                depends_on=("research",),
            ),
        )
    return Workflow(
        id=identifier,
        version=1,
        title=example.title,
        inputs=("documents",),
        nodes=nodes,
        tools=intake.tools,
        constraints=intake.constraints,
        provenance=Provenance(
            kind="synthetic", source="Explicit example replay; not language understanding"
        ),
    )


class ScopedResearchStorage(SqlStorage):
    """Map the lane's public-cache namespace into the authenticated tenant namespace."""

    def __init__(self, storage: PlanningStorage, owner: str) -> None:
        super().__init__(storage.engine)
        self.tenant = owner

    def _id(self, identifier: str) -> str:
        return hashlib.sha256((self.tenant + ":" + identifier).encode()).hexdigest()

    def put(self, owner: str, kind: str, object_id: str, payload: str, version: int = 1) -> None:
        super().put(self.tenant, kind, self._id(object_id), payload, version)

    def get(self, owner: str, kind: str, object_id: str, version: int = 1) -> str:
        return super().get(self.tenant, kind, self._id(object_id), version)


class PlanningService:
    def __init__(self, storage: PlanningStorage, settings: Settings) -> None:
        self.storage, self.settings = storage, settings

    def run(self, owner: str, job: Job) -> None:
        def check() -> None:
            current = self.storage.job(owner, job.id)
            if current.status != "running" or current.attempts != job.attempts:
                raise DomainError(ErrorCode.CONFLICT, "Job cancelled or lease superseded", 409)

        def phase(name: str) -> None:
            check()
            current = self.storage.job(owner, job.id)
            self.storage.update_job(owner, current, phase=name, progress=(*current.progress, name))

        try:
            if self.storage.has_uncertain_call(owner, job):
                self.storage.safe_failure(
                    owner,
                    job,
                    "Previous provider completion/accounting uncertain; operator reconciliation required",
                    True,
                )
                return
            plan = PlanVersion.model_validate_json(
                self.storage.get(owner, "plan", job.workflow_id, job.workflow_version)
            )
            value = plan.input
            phase("validating_interpretation")
            intake = value.intake
            strict = bool(
                re.search(
                    r"local[- ]only|no (?:external|hosted|cloud)|must stay local|air[- ]gapped",
                    intake.description,
                    re.I,
                )
            )
            if strict and (
                value.processing.inference == "approved_hosted" or value.processing.public_research
            ):
                raise DomainError(
                    ErrorCode.UNSUPPORTED,
                    "Explicit no-egress constraint conflicts with processing controls",
                )
            recorded = (
                example_workflow(intake, plan.id)
                if self.settings.mode == "fixture" and value.processing.inference == "local_only"
                else None
            )
            if value.edited_workflow:
                edited = value.edited_workflow
                if edited.constraints != intake.constraints or edited.tools != intake.tools:
                    raise DomainError(
                        ErrorCode.INVALID,
                        "Edited workflow must preserve canonical constraints and tool declarations",
                    )
                SchemaInterpreter._validate_meaning(
                    intake, edited.model_copy(update={"version": 1}), plan.id
                )
                interpreted = Interpretation(status="ready", workflow=edited)
            elif value.proposal_mode == "single_stage":
                interpreted = single_stage(value, plan.id)
            elif recorded:
                interpreted = SchemaInterpreter(
                    RecordedInference((recorded.model_dump_json(),))
                ).interpret(intake, plan.id)
            elif deterministic_workflow(intake, plan.id) is not None:
                interpreted = SchemaInterpreter().interpret(intake, plan.id)
            else:
                # Targeted questions are evaluated before requesting any paid inference.
                questions = unresolved(value)
                if questions:
                    interpreted = Interpretation(status="needs_clarification", questions=questions)
                elif value.processing.inference == "local_model":
                    if not self.settings.local_interpretation_model:
                        raise DomainError(
                            ErrorCode.UNSUPPORTED,
                            "No local interpretation model is configured; no fallback",
                        )
                    phase("interpreting_on_loopback_model")

                    def record_local(metadata: dict[str, str | int | float]) -> None:
                        self.storage.update_job(
                            owner,
                            self.storage.job(owner, job.id),
                            served_configuration=metadata,
                            accounted_usd=0,
                            accounting="known",
                        )

                    proposed, metadata = interpret_local(
                        self.settings.local_interpretation_model,
                        intake,
                        plan.id,
                        str([x.model_dump() for x in value.answers]),
                        check,
                        record_local,
                    )
                    SchemaInterpreter._validate_meaning(intake, proposed, plan.id)
                    self.storage.update_job(
                        owner,
                        self.storage.job(owner, job.id),
                        served_configuration=metadata,
                        accounted_usd=0,
                        accounting="known",
                    )
                    interpreted = Interpretation(status="ready", workflow=proposed)
                else:
                    if (
                        value.processing.inference != "approved_hosted"
                        or self.settings.mode != "live"
                    ):
                        raise DomainError(
                            ErrorCode.UNSUPPORTED,
                            "Free-text interpretation unavailable under current permissions. Use an explicit fixture, deterministic instruction, or validated workflow edit.",
                        )
                    approval = approval_for(
                        self.settings.approvals_file, owner, value.processing.interpretation_role
                    )
                    adapter = OpenRouterRole(
                        approval,
                        self.storage,
                        owner,
                        self.storage.job(owner, job.id),
                        value.processing.max_planning_usd,
                        check,
                    )
                    prompt = (
                        f"Return Workflow JSON for id {plan.id}, version 1, preserving constraints, declared tools, human review and explicit loop bounds. "
                        f"Schema: {Workflow.model_json_schema()}\nUntrusted intake: {intake.model_dump_json()}\nUntrusted clarification answers: {[x.model_dump() for x in value.answers]}"
                    )
                    raw = adapter.complete(role="interpretation", prompt=prompt)
                    interpreted = SchemaInterpreter(
                        RecordedInference((raw,)), max_repairs=0
                    ).interpret(intake, plan.id)
                    if interpreted.workflow:
                        interpreted = interpreted.model_copy(
                            update={
                                "workflow": interpreted.workflow.model_copy(
                                    update={
                                        "provenance": Provenance(
                                            kind="inference",
                                            source="Live authorized control-plane interpretation; schema and semantics validated; not target-model evidence",
                                        )
                                    }
                                )
                            }
                        )
            workflow = interpreted.workflow
            if (
                workflow
                and re.search(r"\buse (?:an? )?(?:llm|language model)\b", intake.description, re.I)
                and not any(n.kind in ("llm", "bounded_agent") for n in workflow.nodes)
            ):
                raise DomainError(
                    ErrorCode.INVALID, "Interpretation omitted an explicitly requested model stage"
                )
            if workflow is None:
                result = PlanningResult(
                    plan_id=plan.id,
                    version=plan.version,
                    interpretation=interpreted,
                    status="needs_clarification" if interpreted.questions else "blocked",
                    fixture=self.settings.mode == "fixture",
                )
            else:
                workflow = Workflow.model_validate(
                    {
                        **workflow.model_dump(),
                        "version": plan.version,
                        "requirements": value.requirements,
                    }
                )
                interpreted = interpreted.model_copy(update={"workflow": workflow})
                model_nodes = any(n.kind in ("llm", "bounded_agent") for n in workflow.nodes)
                phase("pinning_catalog")
                research = None
                missing: list[str] = []
                if not model_nodes:
                    catalog = CatalogSnapshot(
                        id="no-model-catalog",
                        artifacts=(),
                        configurations=(),
                        evidence=(),
                        synthetic=False,
                    )
                elif value.catalog_mode == "approved_runtime":
                    from .runtime_catalog import planning_catalog

                    catalog, target_gaps = planning_catalog(self.settings, owner, value)
                    missing.extend(target_gaps)
                elif value.catalog_mode == "fixture":
                    if self.settings.mode != "fixture":
                        raise DomainError(
                            ErrorCode.UNSUPPORTED, "Synthetic catalog denied in live mode"
                        )
                    catalog = SyntheticCatalog().snapshot()
                elif value.catalog_mode == "runtime_public":
                    if not value.processing.public_research or strict:
                        raise DomainError(
                            ErrorCode.UNSUPPORTED,
                            "Public research egress not permitted; no request made",
                        )
                    phase("fetching_official_public_metadata")
                    sources = public_sources(check)
                    research_plan = ResearchPlan(
                        artifacts=ArtifactInput(repositories=(PUBLIC_REPOSITORY,))
                    )
                    snapshot = PublicResearch(
                        sources=sources,
                        plan=research_plan,
                        storage=ScopedResearchStorage(self.storage, owner),
                    ).run()
                    catalog, research = snapshot.snapshot(), snapshot.ledger()
                    missing.append(
                        "Publisher metadata is not a verified runnable configuration; download/license context, endpoint capabilities, prompt and harness bindings remain unverified."
                    )
                else:
                    captures = json.loads(
                        files("buildbox_router")
                        .joinpath("data/sources-2026-09-06.json")
                        .read_text()
                    )
                    sources = RecordedSources(
                        SourceCapture.model_validate(capture) for capture in captures
                    )
                    research_plan = ResearchPlan.model_validate_json(
                        files("buildbox_router").joinpath("data/plan-2026-09-06.json").read_text()
                    )
                    snapshot = PublicResearch(
                        sources=sources,
                        plan=research_plan,
                        storage=ScopedResearchStorage(self.storage, owner),
                    ).run()
                    catalog, research = snapshot.snapshot(), snapshot.ledger()
                    missing.append(
                        "Retained September 6 public evidence is an offline snapshot, not a live refresh or tested target configuration. Exact configuration bindings and suitability evidence remain missing."
                    )
                if model_nodes and value.catalog_mode != "approved_runtime":
                    requirements = value.requirements
                    if requirements.input_modality == "image":
                        missing.append(
                            "Image-input capability for the exact target configuration is unverified."
                        )
                    if requirements.deployment == "self_hosted":
                        missing.append(
                            "Self-hosted deployment, hardware fit and license context are unverified; provider region is not deployment proof."
                        )
                    if requirements.structured_output or requirements.tool_calling:
                        missing.append(
                            "Required structured-output/tool-call support is unverified for exact target configurations."
                        )
                elif not model_nodes and (
                    value.requirements.input_modality != "text"
                    or value.requirements.structured_output
                    or value.requirements.tool_calling
                ):
                    missing.append(
                        "This no-model text plan does not establish the requested image/structured-output/tool-call capability."
                    )
                phase("deterministic_selection")
                selector = DeterministicSelector()
                filtered = selector.filter(workflow, catalog)
                recommendation = None
                if not missing:
                    try:
                        recommendation = selector.recommend(workflow, catalog, job.id)
                    except DomainError as exc:
                        missing.append(exc.detail.message)
                result = PlanningResult(
                    plan_id=plan.id,
                    version=plan.version,
                    interpretation=interpreted,
                    workflow=workflow,
                    catalog=catalog,
                    research=research,
                    recommendation=recommendation,
                    status="blocked"
                    if recommendation is None
                    else "provisional"
                    if model_nodes
                    else "deterministic",
                    exclusions=filtered.excluded,
                    missing_facts=tuple(missing),
                    assumptions=(
                        "Workflow is a plan only. No tools or described model steps have executed.",
                        "Empty input bindings are unspecified planning gaps, not executable data mappings.",
                    ),
                    fixture=self.settings.mode == "fixture",
                )
            check()
            self.storage.complete_planning(owner, self.storage.job(owner, job.id), result)
        except Exception as exc:
            current = self.storage.job(owner, job.id)
            if current.status == "running" and current.attempts == job.attempts:
                uncertain = self.storage.has_uncertain_call(owner, job)
                self.storage.safe_failure(
                    owner,
                    current,
                    f"Planning failed during {current.phase} ({type(exc).__name__}). A policy/permission gate, unavailable provider, or invalid output prevented completion. No sample success was substituted.",
                    uncertain,
                )
