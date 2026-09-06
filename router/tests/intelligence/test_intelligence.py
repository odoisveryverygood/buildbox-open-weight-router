import pytest
from buildbox_router.contracts import (
    Assignment,
    CandidateConfiguration,
    CatalogSnapshot,
    Constraints,
    Example,
    Fact,
    Intake,
    ModelArtifact,
)
from buildbox_router.errors import DomainError
from buildbox_router.intelligence.fixture import (
    FixtureInterpreter,
    FixtureSelector,
    NoWriteEvaluator,
    SafePolicyCompiler,
)


def catalog(p):
    def candidate(name, value):
        known = Fact[str](value="local", provenance=p)
        return CandidateConfiguration(
            id=name,
            artifact_id="artifact",
            provider=known,
            region=known,
            quantization=known,
            hardware=known,
            prompt_template_ref="prompt",
            harness_ref="harness",
            reasoning_budget=Fact[int](value=0, provenance=p),
            cost_per_1k_tokens=Fact[float](
                value=value, provenance=p, unknown_reason="Missing" if value is None else None
            ),
            latency_ms=Fact[float](value=0, provenance=p),
            provenance=p,
        )

    return CatalogSnapshot(
        id="fixture",
        synthetic=True,
        artifacts=(
            ModelArtifact(
                id="artifact",
                name="Synthetic",
                revision="v1",
                open_weight=Fact[bool](value=True, provenance=p),
                license=Fact[str](value="Synthetic", provenance=p),
                provenance=p,
            ),
        ),
        configurations=(
            candidate("free", 0.0),
            candidate("costly", 9.0),
            candidate("unknown", None),
        ),
        evidence=(),
    )


def test_hard_constraint_excludes_unknown_and_expensive(workflow, provenance):
    result = FixtureSelector().filter(workflow, catalog(provenance))
    assert result.eligible == ("free",)
    assert set(result.excluded) == {"costly", "unknown"}


def test_zero_budget_does_not_mean_unconstrained(workflow, provenance):
    workflow = workflow.model_copy(
        update={"constraints": Constraints(max_cost_per_1k_tokens=0, provenance=provenance)}
    )
    assert FixtureSelector().filter(workflow, catalog(provenance)).eligible == ("free",)


def test_non_model_steps_have_no_assignment(workflow, provenance):
    rec = FixtureSelector().recommend(workflow, catalog(provenance), "rec")
    assert [a.node_id for a in rec.assignments] == ["classify"]
    policy = SafePolicyCompiler().compile(workflow, rec)
    assert policy.status == "draft" and policy.active is False and policy.production_write is False
    assert policy.execution_tools == () and policy.requires_human_approval


def test_policy_rejects_non_model_assignment(workflow, provenance):
    rec = FixtureSelector().recommend(workflow, catalog(provenance), "rec")
    rec = rec.model_copy(
        update={
            "assignments": (
                *rec.assignments,
                Assignment(node_id="review", configuration_id="free", reason="Bad"),
            )
        }
    )
    with pytest.raises(DomainError):
        SafePolicyCompiler().compile(workflow, rec)


def test_policy_allowlist_does_not_export_text_or_credentials(workflow, provenance):
    secret = "SYNTHETIC_SECRET_MARKER_DO_NOT_EXPORT"
    workflow = workflow.model_copy(update={"title": secret})
    rec = FixtureSelector().recommend(workflow, catalog(provenance), "rec")
    rec = rec.model_copy(
        update={
            "assignments": (Assignment(node_id="classify", configuration_id="free", reason=secret),)
        }
    )
    payload = SafePolicyCompiler().compile(workflow, rec).model_dump_json()
    assert secret not in payload
    assert all(
        term not in payload for term in ("api_key", "authorization", "password", "endpoint_url")
    )


def test_fixture_interpretation_refuses_modified_text(provenance):
    intake = Intake(
        example_id="demo",
        description="Fixed example",
        constraints=Constraints(provenance=provenance),
    )
    interpreter = FixtureInterpreter(Example(id="demo", title="Example", intake=intake))
    assert interpreter.interpret(intake, "workflow").status == "ready"
    result = interpreter.interpret(
        intake.model_copy(update={"description": "Send a real invoice now"}), "workflow"
    )
    assert result.status == "needs_clarification" and result.workflow is None


def test_evaluation_does_not_fabricate_a_score(workflow, provenance):
    rec = FixtureSelector().recommend(workflow, catalog(provenance), "rec")
    evaluation = NoWriteEvaluator().evaluate(rec, "holdout-v1")
    assert evaluation.status == "not_run" and evaluation.metric.value is None
