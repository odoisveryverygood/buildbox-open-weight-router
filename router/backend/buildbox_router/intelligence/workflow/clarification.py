"""Versioned decision-impact heuristic, not calibrated information gain.

No shadow answer store: previously answered canonical constraints/tools are read
from the revised Intake. The v1 contract cannot persist richer answer records.
"""

import re

from ...contracts import Clarification, Intake

RULE_VERSION = "clarification-1.0"


def explicit_limits(description: str) -> tuple[int | None, int | None]:
    def find(pattern: str) -> int | None:
        match = re.search(pattern, description, re.IGNORECASE)
        return int(next(value for value in match.groups() if value is not None)) if match else None

    return (
        find(r"max_iterations\s*=\s*(\d+)|at most\s+(\d+)\s+iterations"),
        find(r"(?:max_model_calls\s*=\s*(\d+))")
        if "max_model_calls" in description.lower()
        else find(r"at most\s+(\d+)\s+model calls"),
    )


def numeric_constraints(description: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
    costs = tuple(
        float(x)
        for x in re.findall(
            r"(?:at most|max(?:imum)?(?: cost)?[: =]*)\s*\$?(\d+(?:\.\d+)?)\s*USD\s+per\s+(?:1,?000|1k)\s+tokens",
            description,
            re.IGNORECASE,
        )
    )
    latencies = tuple(
        float(x)
        for x in re.findall(
            r"(?:max(?:imum)? latency[: =]*|at most\s+)(\d+(?:\.\d+)?)\s*ms",
            description,
            re.IGNORECASE,
        )
    )
    return costs, latencies


class ImpactClarifier:
    def blockers(self, intake: Intake) -> tuple[Clarification, ...]:
        """Return every unresolved blocker, in deterministic priority order."""
        text = intake.description.lower()
        questions: list[Clarification] = []

        def add(field: str, question: str) -> None:
            if not any(q.field == field for q in questions):
                questions.append(Clarification(field=field, question=question))

        local_only = bool(
            re.search(
                r"local[- ]only|no (?:external|hosted|cloud)|must stay local|never (?:send|transmit).*external",
                text,
            )
        )
        hosted_required = bool(
            re.search(r"must (?:use|call).*hosted|require(?:s|d)? (?:a )?hosted", text)
        )
        if local_only and hosted_required:
            add(
                "constraints.egress_conflict",
                "Which hard instruction should change: local-only or required hosted processing? This determines whether any processing architecture is admissible; neither instruction is silently dropped.",
            )
        regions = tuple(re.findall(r"\bregion\s*[:=]\s*([a-z][a-z0-9_-]*)", text))
        if len(set(regions)) > 1 or (
            regions
            and intake.constraints.required_region is not None
            and any(r != intake.constraints.required_region.lower() for r in regions)
        ):
            add(
                "constraints.region_conflict",
                "Resolve conflicting required regions before selection. Region eligibility cannot be silently widened or replaced.",
            )
        elif regions and intake.constraints.required_region is None:
            add(
                "constraints.region_confirmation",
                "Confirm the requested region in the canonical constraints field; it changes endpoint eligibility and does not itself establish privacy.",
            )
        costs, latencies = numeric_constraints(intake.description)
        for name, values, known in (
            ("cost", costs, intake.constraints.max_cost_per_1k_tokens),
            ("latency", latencies, intake.constraints.max_latency_ms),
        ):
            if len(set(values)) > 1 or (
                values and known is not None and any(v != known for v in values)
            ):
                add(
                    f"constraints.{name}_conflict",
                    f"Resolve the conflicting hard {name} limits in the text and structured answers. The limit changes candidate eligibility.",
                )
            elif values and known is None:
                add(
                    f"constraints.{name}_confirmation",
                    f"Confirm the stated {name} limit in the canonical constraints field. This controls a hard exclusion; the interpreter will not silently insert an unconfirmed limit.",
                )
        tool_text = re.sub(
            r"\b(?:never|do not|don't)\s+(?:send|browse|search|retrieve)\b", "", text
        )
        requests_tools = bool(
            re.search(
                r"\b(?:search|browse|retrieve|send)\b|\b(?:use|with|call)\s+(?:a\s+)?tool\b|\bissue (?:a )?refund\b|\bupdate (?:the )?(?:crm|database)\b",
                tool_text,
            )
        )
        if requests_tools and not intake.tools:
            add(
                "tools",
                "Which tools are actually available, as opposed to requested? Declare approved tool IDs; this determines tool-stage feasibility and never grants execution permission.",
            )
        if requests_tools and re.search(r"no tools|without any tools", text):
            add(
                "constraints.tool_conflict",
                "Resolve the tool request versus the no-tools instruction. This determines whether a tool stage may appear at all.",
            )
        if re.search(r"\b(?:agent|loop|repeat|until)\b", text):
            for label, pattern in (
                ("iterations", r"max_iterations\s*=\s*(\d+)|at most\s+(\d+)\s+iterations"),
                ("model_calls", r"max_model_calls\s*=\s*(\d+)|at most\s+(\d+)\s+model calls"),
            ):
                stated = {int(a or b) for a, b in re.findall(pattern, text)}
                if len(stated) > 1:
                    add(
                        "workflow.loop_conflict",
                        f"Resolve conflicting {label} bounds before creating the bounded agent. Neither hard limit is silently selected.",
                    )
            iterations, calls = explicit_limits(intake.description)
            if iterations is None or calls is None:
                add(
                    "workflow.loop_bounds",
                    "Specify maximum iterations and maximum model calls, plus a stopping condition, for the bounded agent. These are upper bounds, not known actual call counts.",
                )
            elif not (1 <= iterations <= 10 and 1 <= calls <= 20):
                add(
                    "workflow.loop_bounds",
                    "The supported loop bounds are 1–10 iterations and 1–20 model calls. Revise the request or split the scope; the outer graph must remain acyclic.",
                )
            if not re.search(r"\b(?:stop|until)\b", text):
                add(
                    "workflow.termination",
                    "What condition stops the bounded agent before its hard limit? This determines termination behavior; a target outcome alone does not establish a safe loop.",
                )
        if re.search(
            r"(?:total|monthly|per workflow|per document|per run).{0,30}(?:budget|cost)|(?:budget|cost).{0,30}(?:total|monthly|per workflow|per document|per run)",
            text,
        ):
            add(
                "constraints.workflow_budget",
                "A hard workflow budget needs call/token/retry assumptions and all billed components. v1 cannot represent those quantities; the budget check and model assignment must remain blocked pending the contract extension.",
            )
        if re.search(r"\b(?:improve|optimize|automate) (?:it|everything|my business)\b", text):
            add(
                "workflow.objective",
                "What specific transformation should this workflow perform? The objective determines whether it needs code, a model, a tool, or is outside supported scope.",
            )
        if not re.search(
            r"\b(?:text|document|documents|invoice|invoices|ticket|tickets|question|questions|email|emails|csv|json|lines|records|pdf|image|images|audio|input|support|research|topic)\b",
            text,
        ):
            add(
                "workflow.inputs",
                "What input does the workflow receive? Input form changes architecture and model capability requirements.",
            )
        if not re.search(
            r"\b(?:return|output|produce|extract|classify|classification|summarize|summary|sort|lowercase|uppercase|trim|deduplicate|convert|translate|answer|draft)\b",
            text,
        ):
            add(
                "workflow.outputs",
                "What should the workflow return? Output shape determines deterministic versus model stages and required output capabilities.",
            )
        # Quality/cost/latency are not invented; missing optional preferences are not blockers.
        if re.search(
            r"\b(?:accurate(?:ly)?|accuracy|quality|reliable|correct)\b", text
        ) and not re.search(r"success:|accepted when|rubric:|measured by", text):
            add(
                "workflow.success_criteria",
                "How is acceptable quality measured on your workload? This affects evaluation and release eligibility; no numeric quality threshold is assumed.",
            )
        return tuple(questions)

    def clarify(self, intake: Intake) -> tuple[Clarification, ...]:
        return self.blockers(intake)[:3]
