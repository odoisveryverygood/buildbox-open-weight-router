import pytest
from buildbox_router.contracts import Fact, Node, Workflow
from pydantic import ValidationError


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "missing",
        "cycle",
        "bad_binding",
        "undeclared_tool",
        "unbounded",
        "self",
        "unknown_output",
    ],
)
def test_invalid_graphs_are_rejected(workflow, change):
    data = workflow.model_dump(mode="json")
    if change == "duplicate":
        data["nodes"].append(data["nodes"][0])
    elif change == "missing":
        data["nodes"][0]["depends_on"] = ["missing"]
    elif change == "cycle":
        data["nodes"][0]["depends_on"] = ["review"]
    elif change == "self":
        data["nodes"][0]["depends_on"] = ["classify"]
    elif change == "bad_binding":
        data["nodes"][0]["inputs"]["text"]["source"] = "missing"
    elif change == "unknown_output":
        data["nodes"][1]["inputs"] = {"category": {"source": "classify", "output": "missing"}}
    elif change == "undeclared_tool":
        data["nodes"][1]["kind"] = "tool"
        data["nodes"][1]["tool_id"] = "undeclared"
    elif change == "unbounded":
        data["nodes"][0]["kind"] = "bounded_agent"
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


def test_bounded_agent_accepted_and_budget_enforced(workflow):
    data = workflow.model_dump(mode="json")
    data["nodes"][0].update(kind="bounded_agent", max_iterations=2, max_model_calls=3)
    assert Workflow.model_validate(data).nodes[0].max_iterations == 2
    data["nodes"][0]["max_iterations"] = 1000
    with pytest.raises(ValidationError):
        Workflow.model_validate(data)


def test_unknown_differs_from_false_and_zero(provenance):
    unknown = Fact[bool](provenance=provenance, unknown_reason="Not observed")
    false = Fact[bool](value=False, provenance=provenance)
    zero = Fact[float](value=0, provenance=provenance)
    assert unknown.value is None and false.value is False and zero.value == 0
    assert unknown.model_dump_json() != false.model_dump_json()
    with pytest.raises(ValidationError):
        Fact[bool](provenance=provenance)


def test_non_model_schema_rejects_assignment_field():
    with pytest.raises(ValidationError):
        Node(id="approval", kind="human_approval", purpose="Review", model_id="bad")
