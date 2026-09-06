"""Cost components only. No implicit tokens, retries, tools or invented savings."""

import math

from ...contracts import Fact, Provenance, Workflow


def token_component_cost(price_per_1k: Fact[float], tokens: Fact[int]) -> Fact[float]:
    provenance = Provenance(
        kind="inference",
        source="estimate-1.0: token component = price_per_1k * tokens / 1000, in supplied price units; currency unspecified, not total workflow spend",
        evidence_ids=tuple(
            sorted(set(price_per_1k.provenance.evidence_ids + tokens.provenance.evidence_ids))
        ),
    )
    if price_per_1k.value is None or tokens.value is None:
        return Fact[float](
            provenance=provenance,
            unknown_reason="Price or token quantity missing; unavailable, not zero",
        )
    if not math.isfinite(price_per_1k.value) or price_per_1k.value < 0 or tokens.value < 0:
        return Fact[float](provenance=provenance, unknown_reason="Invalid price or quantity")
    return Fact[float](value=price_per_1k.value * tokens.value / 1000, provenance=provenance)


def projected_workflow_spend(workflow: Workflow) -> Fact[float]:
    return Fact[float](
        provenance=Provenance(
            kind="inference",
            source="estimate-1.0: projected customer workflow spend, separate from planning/evaluation",
        ),
        unknown_reason="v1 does not carry actual calls, tokens, retries, tool prices or extra billed components; logical stages and loop upper bounds do not establish a total budget",
    )
