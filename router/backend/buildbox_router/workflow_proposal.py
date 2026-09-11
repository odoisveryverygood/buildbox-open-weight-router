"""Local disclosed one-model proposal. No inference, tools, or implicit authority."""

import re

from .contracts import Binding, Clarification, Interpretation, Node, Provenance, Workflow
from .intelligence.workflow.clarification import ImpactClarifier
from .planning_contracts import PlanInput


def unresolved(value: PlanInput) -> tuple[Clarification, ...]:
    answered = {
        a.question_id
        for a in value.answers
        if a.answer.strip().lower() not in {"unknown", "unsure", "not sure", "?"}
    }
    descriptive = {
        "workflow.inputs",
        "workflow.outputs",
        "workflow.objective",
        "workflow.success_criteria",
    }
    # Notes can answer descriptive questions, never relax a hard gate or declare a tool.
    return tuple(
        q
        for q in ImpactClarifier().blockers(value.intake)
        if q.field not in answered or q.field not in descriptive
    )[:3]


def single_stage(value: PlanInput, identifier: str) -> Interpretation:
    questions = unresolved(value)
    if questions:
        return Interpretation(status="needs_clarification", questions=questions)
    if value.intake.tools or re.search(
        r"\b(?:agent|loop|repeat|until|no model|no llm|without a model|without an llm)\b",
        value.intake.description,
        re.I,
    ):
        return Interpretation(
            status="needs_clarification",
            questions=(
                Clarification(
                    field="workflow.graph",
                    question="This one-model proposal cannot execute tools or loops. Supply an explicit bounded graph, or revise the objective to process supplied text only. Tool declarations are not connections.",
                ),
            ),
        )
    notes = "\n".join(f"{a.question_id}: {a.answer}" for a in value.answers)
    nodes = [
        Node(
            id="respond",
            kind="llm",
            purpose=(value.intake.description + "\n" + notes).strip(),
            inputs={"input": Binding(source="input", output="value", from_input=True)},
        )
    ]
    if re.search(r"human (?:review|approval)|ask a human", value.intake.description, re.I):
        nodes.append(
            Node(
                id="review",
                kind="human_approval",
                purpose="Pause for requested human review; no automatic approval",
                depends_on=("respond",),
                inputs={"result": Binding(source="respond", output="result")},
            )
        )
    return Interpretation(
        status="ready",
        workflow=Workflow(
            id=identifier,
            version=1,
            title=value.intake.description[:160],
            inputs=("input",),
            nodes=tuple(nodes),
            constraints=value.intake.constraints,
            tools=value.intake.tools,
            provenance=Provenance(
                kind="inference",
                source="single-stage-proposal-v1: explicit local template, not language-model interpretation. Review text input/result bindings and prompt before execution. One model may suffice; quality unknown.",
            ),
        ),
    )
