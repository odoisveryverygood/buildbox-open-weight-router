from ..contracts import (
    Assignment,
    Binding,
    CatalogSnapshot,
    Clarification,
    DraftPolicy,
    ErrorCode,
    EvaluationRun,
    Example,
    Fact,
    FilterResult,
    Intake,
    Interpretation,
    Node,
    Provenance,
    Recommendation,
    StackComparison,
    Workflow,
)
from ..errors import DomainError


class FixtureInterpreter:
    """Exact example selection, deliberately NOT natural-language parsing."""

    def __init__(self, example: Example) -> None:
        self.example = example

    def clarify(self, intake: Intake) -> tuple[Clarification, ...]:
        if (
            intake.example_id != self.example.id
            or intake.description != self.example.intake.description
        ):
            return (
                Clarification(
                    field="example_id",
                    question="Select the unchanged synthetic example; arbitrary workflow interpretation is not implemented.",
                ),
            )
        return ()

    def interpret(self, intake: Intake, workflow_id: str) -> Interpretation:
        questions = self.clarify(intake)
        if questions:
            return Interpretation(status="needs_clarification", questions=questions)
        return Interpretation(
            status="ready",
            workflow=Workflow(
                id=workflow_id,
                version=1,
                title=self.example.title,
                inputs=("document",),
                tools=intake.tools,
                constraints=intake.constraints,
                provenance=Provenance(
                    kind="synthetic", source="Explicit built-in example, not parsed text"
                ),
                nodes=(
                    Node(
                        id="normalize",
                        kind="code",
                        purpose="Describe whitespace normalization; never execute",
                        inputs={
                            "text": Binding(source="document", output="value", from_input=True)
                        },
                    ),
                    Node(
                        id="classify",
                        kind="llm",
                        purpose="Assign a synthetic document category",
                        depends_on=("normalize",),
                        inputs={"text": Binding(source="normalize", output="result")},
                    ),
                    Node(
                        id="review",
                        kind="human_approval",
                        purpose="Human reviews proposed output",
                        depends_on=("classify",),
                        inputs={"category": Binding(source="classify", output="result")},
                    ),
                ),
            ),
        )


class FixtureSelector:
    def filter(self, workflow: Workflow, catalog: CatalogSnapshot) -> FilterResult:
        artifacts = {a.id: a for a in catalog.artifacts}
        eligible: list[str] = []
        excluded: dict[str, tuple[str, ...]] = {}
        constraints = workflow.constraints
        for candidate in catalog.configurations:
            reasons: list[str] = []
            if (
                constraints.open_weight_required
                and artifacts[candidate.artifact_id].open_weight.value is not True
            ):
                reasons.append("Open weights required; false or unknown is ineligible")
            for name, fact, limit in (
                ("cost", candidate.cost_per_1k_tokens, constraints.max_cost_per_1k_tokens),
                ("latency", candidate.latency_ms, constraints.max_latency_ms),
            ):
                if limit is not None and (fact.value is None or fact.value > limit):
                    reasons.append(f"Hard {name} ceiling not established")
            if (
                constraints.required_region is not None
                and candidate.region.value != constraints.required_region
            ):
                reasons.append("Required locality not established")
            if reasons:
                excluded[candidate.id] = tuple(reasons)
            else:
                eligible.append(candidate.id)
        return FilterResult(eligible=tuple(eligible), excluded=excluded)

    def rank(
        self, workflow: Workflow, catalog: CatalogSnapshot, result: FilterResult
    ) -> tuple[str, ...]:
        eligible = [c for c in catalog.configurations if c.id in result.eligible]
        # Unknown sorts last; zero remains zero. No invented quality scores.
        eligible.sort(
            key=lambda c: (
                c.cost_per_1k_tokens.value
                if c.cost_per_1k_tokens.value is not None
                else float("inf"),
                c.id,
            )
        )
        return tuple(c.id for c in eligible)

    def compare(self, catalog: CatalogSnapshot, ranked: tuple[str, ...]) -> StackComparison:
        return StackComparison(
            configuration_ids=ranked[:3],
            rationale="Synthetic cost order after hard filters; quality not measured",
        )

    def recommend(
        self, workflow: Workflow, catalog: CatalogSnapshot, recommendation_id: str
    ) -> Recommendation:
        if not catalog.synthetic:
            raise DomainError(
                ErrorCode.UNSUPPORTED, "Fixture selector requires a synthetic snapshot"
            )
        filtered = self.filter(workflow, catalog)
        ranked = self.rank(workflow, catalog, filtered)
        if not ranked:
            raise DomainError(
                ErrorCode.INVALID, "No configuration satisfies known hard constraints"
            )
        return Recommendation(
            id=recommendation_id,
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            catalog_id=catalog.id,
            assignments=tuple(
                Assignment(
                    node_id=n.id,
                    configuration_id=ranked[0],
                    reason="Lowest synthetic cost among eligible configurations; quality unknown",
                )
                for n in workflow.nodes
                if n.kind in ("llm", "bounded_agent")
            ),
            alternatives=self.compare(catalog, ranked).configuration_ids[1:],
            filter_result=filtered,
            evidence_ids=tuple(e.id for e in catalog.evidence),
            confidence="synthetic_only",
            limitations=(
                "Invented configurations: not real models or prices",
                "No customer evaluation or business action executed",
                "No production suitability established",
            ),
        )


class SafePolicyCompiler:
    def compile(self, workflow: Workflow, recommendation: Recommendation) -> DraftPolicy:
        if (workflow.id, workflow.version) != (
            recommendation.workflow_id,
            recommendation.workflow_version,
        ):
            raise DomainError(ErrorCode.INVALID, "Recommendation/workflow version mismatch")
        required = {n.id for n in workflow.nodes if n.kind in ("llm", "bounded_agent")}
        assignments = recommendation.assignments
        if {a.node_id for a in assignments} != required or len(assignments) != len(required):
            raise DomainError(
                ErrorCode.INVALID, "Assign each model-using node once, and no other nodes"
            )
        if any(
            a.configuration_id not in recommendation.filter_result.eligible for a in assignments
        ):
            raise DomainError(ErrorCode.INVALID, "Assignment not eligible")
        # Allowlist-only export; do not include user text, endpoints, tool connections or rationale.
        sanitized = tuple(
            Assignment(
                node_id=a.node_id,
                configuration_id=a.configuration_id,
                reason="Pending controlled evaluation and human approval",
            )
            for a in assignments
        )
        return DraftPolicy(
            id=f"policy-{recommendation.id}",
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            recommendation_id=recommendation.id,
            assignments=sanitized,
            synthetic=recommendation.confidence == "synthetic_only",
        )


class NoWriteEvaluator:
    def evaluate(self, recommendation: Recommendation, holdout_ref: str) -> EvaluationRun:
        return EvaluationRun(
            id=f"eval-{recommendation.id}",
            recommendation_id=recommendation.id,
            status="not_run",
            holdout_ref=holdout_ref,
            metric=Fact[float](
                provenance=Provenance(kind="synthetic", source="No inference performed"),
                unknown_reason="Evaluation transport intentionally disabled",
            ),
            synthetic=True,
        )
