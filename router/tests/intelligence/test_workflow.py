import json
from pathlib import Path

import pytest
from buildbox_router.contracts import (
    Binding,
    Constraints,
    Intake,
    Node,
    Provenance,
    Workflow,
    WorkflowTool,
)
from buildbox_router.errors import DomainError
from buildbox_router.intelligence.workflow import (
    ImpactClarifier,
    RecordedInference,
    SchemaInterpreter,
    persist_revision,
    revise_workflow,
)

FIXTURES = json.loads(Path(__file__).with_name("intakes.json").read_text())


def intake_for(case):
    return Intake(
        description=case["text"],
        constraints=Constraints(
            provenance=Provenance(kind="user_declared", source="Synthetic test user answers")
        ),
        tools=tuple(
            WorkflowTool(id=t, description="User-declared synthetic tool; not connected")
            for t in case.get("tools", [])
        ),
    )


def recorded_workflow(case, intake):
    shape = case.get("shape", "llm")
    nodes = []
    if shape == "tool":
        nodes.append(
            Node(
                id="lookup",
                kind="tool",
                purpose="Retrieve user-declared context",
                tool_id=intake.tools[0].id,
                inputs={"query": Binding(source="text", output="value", from_input=True)},
            )
        )
    if shape == "agent":
        nodes.append(
            Node(
                id="classify",
                kind="bounded_agent",
                purpose="Bounded review; stop on stated condition or the explicit cap",
                max_iterations=case.get("iterations", 2),
                max_model_calls=case.get("calls", 3),
                allowed_tools=tuple(t.id for t in intake.tools),
                inputs={"input": Binding(source="text", output="value", from_input=True)},
            )
        )
    else:
        nodes.append(
            Node(
                id="classify",
                kind="code" if shape in ("code", "code_human") else "llm",
                purpose="Return JSON fields" if shape == "json" else case["text"],
                depends_on=("lookup",) if shape == "tool" else (),
                inputs={
                    "text": Binding(source="lookup", output="result")
                    if shape == "tool"
                    else Binding(source="text", output="value", from_input=True)
                },
            )
        )
    if shape in ("human", "code_human", "tool") or "human approval" in case["text"]:
        nodes.append(
            Node(
                id="review",
                kind="human_approval",
                purpose="Human checks output",
                depends_on=("classify",),
            )
        )
    return Workflow(
        id="workflow-test",
        version=1,
        title=case["text"],
        inputs=("text",),
        nodes=tuple(nodes),
        tools=intake.tools,
        constraints=intake.constraints,
        provenance=Provenance(kind="synthetic", source="Recorded response, not observed parsing"),
    )


@pytest.mark.parametrize("case", FIXTURES, ids=[c["id"] for c in FIXTURES])
def test_thirty_varied_intakes(case):
    intake = intake_for(case)
    replay = RecordedInference([recorded_workflow(case, intake).model_dump_json()])
    result = SchemaInterpreter(replay).interpret(intake, "workflow-test")
    assert result.status == case["expected"]
    if result.workflow:
        assert result.workflow.constraints == intake.constraints
        assert result.workflow.tools == intake.tools
        assert all(t.connected is False for t in result.workflow.tools)
    if case.get("shape") == "code":
        assert replay.calls == 0 and all(n.kind == "code" for n in result.workflow.nodes)
    if result.status != "ready":
        assert replay.calls == 0


def test_repairs_are_bounded_and_validated(workflow):
    intake = Intake(
        description="Classify text and return a category.", constraints=workflow.constraints
    )
    replay = RecordedInference(['{"truncated":', "not json", workflow.model_dump_json()])
    with pytest.raises(DomainError):
        SchemaInterpreter(replay, max_repairs=1).interpret(intake, workflow.id)
    assert replay.calls == 2
    replay = RecordedInference(['{"truncated":', workflow.model_dump_json()])
    result = SchemaInterpreter(replay, max_repairs=1).interpret(intake, workflow.id)
    assert replay.calls == 2 and result.workflow.id == workflow.id


@pytest.mark.parametrize(
    "response,code",
    [
        (json.dumps({"refusal": "Private provider message"}), None),
        (json.dumps({"schema_version": "99"}), "unsupported_mode"),
        (TimeoutError("private timeout"), "unsupported_mode"),
        (RuntimeError("private credentials"), "unsupported_mode"),
        ("[]", "invalid_request"),
        ("x" * 65537, "invalid_request"),
    ],
)
def test_typed_failures_never_echo_provider_content(workflow, response, code):
    intake = Intake(
        description="Classify text and return a category.", constraints=workflow.constraints
    )
    replay = RecordedInference([response])
    if code is None:
        assert SchemaInterpreter(replay).interpret(intake, workflow.id).status == "unsupported"
    else:
        with pytest.raises(DomainError) as exc:
            SchemaInterpreter(replay, max_repairs=0).interpret(intake, workflow.id)
        assert exc.value.detail.code.value == code
        assert "private" not in str(exc.value).lower()
    assert replay.calls == 1


@pytest.mark.parametrize(
    "description",
    [
        "Classify private text; never send externally; return a label.",
        "Classify text; hosted processing is allowed; return a label.",
    ],
)
def test_egress_denied_before_intake_transmission(workflow, description):
    class ExternalSpy:
        calls = 0

        def complete(self, **kwargs):
            self.calls += 1
            raise AssertionError("Must never be called")

    spy = ExternalSpy()
    with pytest.raises(DomainError, match="Egress denied"):
        SchemaInterpreter(spy).interpret(
            Intake(description=description, constraints=workflow.constraints), workflow.id
        )
    assert spy.calls == 0


def test_unknown_model_tools_and_invented_limits_rejected(workflow):
    intake = Intake(
        description="Classify text and return a category.", constraints=workflow.constraints
    )
    modified = workflow.model_dump(mode="json")
    modified["tools"] = [
        WorkflowTool(id="invented", description="Not provided").model_dump(mode="json")
    ]
    with pytest.raises(DomainError):
        SchemaInterpreter(RecordedInference([json.dumps(modified)]), max_repairs=0).interpret(
            intake, workflow.id
        )
    modified = workflow.model_dump(mode="json")
    modified["nodes"][0].update(kind="bounded_agent", max_iterations=2, max_model_calls=3)
    with pytest.raises(DomainError):
        SchemaInterpreter(RecordedInference([json.dumps(modified)]), max_repairs=0).interpret(
            intake, workflow.id
        )


def test_answer_reuse_and_contradictions(provenance):
    constraints = Constraints(max_cost_per_1k_tokens=1, provenance=provenance)
    intake = Intake(
        description="Summarize text at most 1 USD per 1000 tokens.", constraints=constraints
    )
    assert not ImpactClarifier().clarify(intake)
    changed = intake.model_copy(
        update={"description": "Summarize text at most 2 USD per 1000 tokens."}
    )
    assert ImpactClarifier().clarify(changed)[0].field == "constraints.cost_conflict"
    assert changed.constraints.max_cost_per_1k_tokens == 1


def test_initial_round_capped_all_blockers_retained(provenance):
    intake = Intake(
        description="Automate my business with an agent; search until done; must stay local and must use hosted processing.",
        constraints=Constraints(provenance=provenance),
    )
    clarifier = ImpactClarifier()
    assert len(clarifier.clarify(intake)) == 3
    assert len(clarifier.blockers(intake)) > 3
    assert clarifier.clarify(intake) == clarifier.blockers(intake)[:3]


def test_revisions_preserve_old_versions_and_constraints(storage, provenance):
    old_intake = Intake(
        description="Lowercase text.",
        constraints=Constraints(max_cost_per_1k_tokens=1, provenance=provenance),
    )
    interpreter = SchemaInterpreter()
    old = interpreter.interpret(old_intake, "versioned").workflow
    storage.put("owner", "workflow", old.id, old.model_dump_json())
    revised_intake = old_intake.model_copy(update={"description": "Uppercase text."})
    revised = revise_workflow(old, revised_intake, interpreter).workflow
    persist_revision(storage, "owner", old, revised)
    assert revised.version == 2 and old.version == 1
    assert revised.constraints == old.constraints
    assert Workflow.model_validate_json(storage.get("owner", "workflow", old.id, 1)) == old
    with pytest.raises(DomainError):
        persist_revision(storage, "owner", old, revised)


@pytest.mark.parametrize(
    "description",
    [
        "Classify text in region: eu and region: us; return a label.",
        "An agent classifies text; max_iterations=2 and max_iterations=4; max_model_calls=3; stop on success; return a category.",
    ],
)
def test_conflicting_regions_and_loop_limits_never_silently_resolve(provenance, description):
    intake = Intake(description=description, constraints=Constraints(provenance=provenance))
    result = SchemaInterpreter().interpret(intake, "workflow")
    assert result.status == "needs_clarification"
    assert any("conflict" in q.field for q in result.questions)


def test_schema_rejects_hidden_fields_and_repairs_without_weakening(workflow):
    intake = Intake(
        description="Classify text and return a category.", constraints=workflow.constraints
    )
    raw = workflow.model_dump(mode="json")
    raw["source_spans"] = [{"start": 0, "end": 4}]
    replay = RecordedInference([json.dumps(raw), workflow.model_dump_json()])
    result = SchemaInterpreter(replay).interpret(intake, workflow.id)
    assert replay.calls == 2 and result.status == "ready"
    assert "source_spans" not in result.workflow.model_dump()


def test_prior_job_and_recommendation_stay_pinned_on_revision(storage, workflow, lane_catalog):
    import time

    from buildbox_router.contracts import Job
    from buildbox_router.intelligence.selection import DeterministicSelector

    storage.put("owner", "workflow", workflow.id, workflow.model_dump_json())
    old_job = Job(
        id="old-job",
        workflow_id=workflow.id,
        workflow_version=1,
        status="queued",
        created_at=time.time(),
        updated_at=time.time(),
    )
    storage.enqueue("owner", old_job)
    recommendation = DeterministicSelector().recommend(workflow, lane_catalog, "old-rec")
    storage.put("owner", "recommendation", recommendation.id, recommendation.model_dump_json())
    revised = workflow.model_copy(update={"version": 2, "title": "Edited objective"})
    persist_revision(storage, "owner", workflow, revised)
    assert storage.job("owner", old_job.id).workflow_version == 1
    assert (
        json.loads(storage.get("owner", "recommendation", recommendation.id))["workflow_version"]
        == 1
    )


def test_deterministic_replay_does_not_depend_on_fixture_example_id(workflow):
    intake = Intake(
        description="Classify the support text and return its category.",
        constraints=workflow.constraints,
    )
    outputs = [
        SchemaInterpreter(RecordedInference([workflow.model_dump_json()])).interpret(
            intake, workflow.id
        )
        for _ in range(2)
    ]
    assert intake.example_id is None and outputs[0] == outputs[1]


@pytest.mark.parametrize(
    "description,mutation",
    [
        ("Classify text and require human approval.", "omit_human"),
        ("Lowercase text without a model and return text.", "keep_model"),
        ("Classify text and return a category.", "weaken_budget"),
    ],
)
def test_model_cannot_drop_hard_architecture_or_budget_requirements(
    workflow, description, mutation
):
    intake = Intake(description=description, constraints=workflow.constraints)
    raw = workflow.model_dump(mode="json")
    if mutation == "omit_human":
        raw["nodes"] = raw["nodes"][:1]
    elif mutation == "weaken_budget":
        raw["constraints"]["max_cost_per_1k_tokens"] = None
    replay = RecordedInference([json.dumps(raw)])
    with pytest.raises(DomainError):
        SchemaInterpreter(replay, max_repairs=0).interpret(intake, workflow.id)
    assert replay.calls == 1
