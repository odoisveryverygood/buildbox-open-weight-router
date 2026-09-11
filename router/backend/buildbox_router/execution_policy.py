"""Draft-only policy variants using the existing selector; never route mutation."""

from .contracts import CatalogSnapshot, ErrorCode
from .errors import DomainError
from .execution_contracts import ExecutablePolicy, ExecutableStage, PolicyVariant, VariantRequest
from .ports import Selector


def variant(
    policy: ExecutablePolicy, catalog: CatalogSnapshot, request: VariantRequest, selector: Selector
) -> ExecutablePolicy:
    if catalog.id != policy.catalog_id or request.id == policy.id:
        raise DomainError(
            ErrorCode.CONFLICT, "Variant needs the pinned catalog and a new policy ID", 409
        )
    filtered = selector.filter(policy.workflow, catalog)
    ranked = selector.rank(policy.workflow, catalog, filtered)
    configs = {c.id: c for c in catalog.configurations}
    if request.mode == "cost_conscious":
        ranked = tuple(
            sorted(
                ranked,
                key=lambda c: (
                    configs[c].cost_per_1k_tokens.value is None,
                    configs[c].cost_per_1k_tokens.value
                    if configs[c].cost_per_1k_tokens.value is not None
                    else float("inf"),
                    c,
                ),
            )
        )
    stages = []
    for stage in policy.stages:
        if stage.configuration_id is None:
            stages.append(stage)
            continue
        if not ranked:
            raise DomainError(
                ErrorCode.UNSUPPORTED, "No evidence-admissible configuration for draft variant", 403
            )
        # Keep operator restrictions/budgets, omit fallbacks rather than guessing
        # endpoint capability or reserve bounds. Runtime rechecks every dispatch.
        data = stage.model_dump()
        data.update(configuration_id=ranked[0], fallback_configuration_ids=())
        data["budget"] = stage.budget.model_copy(update={"max_attempts": 1, "max_model_calls": 1})
        stages.append(ExecutableStage.model_validate(data))
    return ExecutablePolicy.model_validate(
        policy.model_dump()
        | {
            "id": request.id,
            "version": 1,
            "stages": stages,
            "quality": "untested_provisional",
            "variant": PolicyVariant(
                mode=request.mode,
                rationale=(
                    "Existing selector eligibility and stable ranking; runtime endpoint/grant/budget checks remain mandatory.",
                    "Cost-conscious uses declared normalized token price, not projected savings; unknown is last."
                    if request.mode == "cost_conscious"
                    else "Quality and balanced share the selector heuristic without comparable workload measurements; neither establishes quality.",
                    "New DRAFT policy only. No alias, admission, production traffic, or active version changes. Fallbacks require separate validated pins.",
                ),
            ),
        }
    )
