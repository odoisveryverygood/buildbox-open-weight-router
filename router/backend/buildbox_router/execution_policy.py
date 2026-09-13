"""Draft-only policy variants using the existing selector; never route mutation."""

import re

from .contracts import CatalogSnapshot, ErrorCode
from .errors import DomainError
from .execution_contracts import (
    ExecutablePolicy,
    ExecutableStage,
    JsonSchemaFormat,
    PolicyEditRequest,
    PolicyVariant,
    PromptRevision,
    ResponseFormat,
    VariantRequest,
    VersionRef,
)
from .ports import Selector


def edit(
    policy: ExecutablePolicy,
    catalog: CatalogSnapshot,
    request: PolicyEditRequest,
    selector: Selector,
) -> ExecutablePolicy:
    """Propose only. Explicit stage edits keep every other pin unchanged."""
    if catalog.id != policy.catalog_id:
        raise DomainError(ErrorCode.CONFLICT, "Pinned catalog required", 409)
    stages = {s.node_id: s for s in policy.stages}
    cheaper = set(request.cheaper_stage_ids)
    kept = None
    if request.instruction.strip():
        match = re.fullmatch(
            r"(?:keep the (.+?) model but )?make (.+?) cheaper[.!]?",
            request.instruction.strip(),
            re.I,
        )
        if not match:
            raise DomainError(
                ErrorCode.INVALID,
                "Use structured edits, or 'keep the STAGE model but make STAGE cheaper'. Unrecognized instructions are not silently applied",
                422,
            )

        def resolve(label: str) -> str:
            matches = [
                n.id
                for n in policy.workflow.nodes
                if n.kind == "llm"
                and (n.id.lower() == label.lower() or label.lower() in n.purpose.lower())
            ]
            if len(matches) != 1:
                raise DomainError(
                    ErrorCode.INVALID, "Stage reference is ambiguous; use the exact stage ID", 422
                )
            return matches[0]

        selected = resolve(match[2])
        kept = resolve(match[1]) if match[1] else None
        if kept == selected:
            raise DomainError(ErrorCode.INVALID, "Cannot keep and change the same stage", 422)
        cheaper.add(selected)
    changed = (
        set(request.pins) | set(request.prompt_templates) | set(request.output_schemas) | cheaper
    )
    if not changed <= stages.keys() or any(not stages[n].configuration_id for n in changed):
        raise DomainError(ErrorCode.INVALID, "Edits must name existing LLM stages", 422)
    excluded = set(request.exclude_configuration_ids)
    if kept and (
        kept in cheaper
        or stages[kept].configuration_id in excluded
        or request.pins.get(kept, stages[kept].configuration_id) != stages[kept].configuration_id
    ):
        raise DomainError(ErrorCode.INVALID, "Structured edits conflict with the kept model", 422)
    if not excluded <= {c.id for c in catalog.configurations}:
        raise DomainError(
            ErrorCode.INVALID, "Excluded configuration is not in the pinned catalog", 422
        )
    filtered = selector.filter(policy.workflow, catalog)
    ranked = [c for c in selector.rank(policy.workflow, catalog, filtered) if c not in excluded]
    if any(c not in ranked for c in request.pins.values()):
        raise DomainError(ErrorCode.UNSUPPORTED, "Pin is excluded or lacks mandatory evidence", 403)
    prompts = []
    compiled = []
    for stage in policy.stages:
        data = stage.model_dump()
        if stage.configuration_id:
            config = request.pins.get(stage.node_id, stage.configuration_id)
            if stage.node_id in cheaper or config in excluded:
                if not ranked:
                    raise DomainError(ErrorCode.UNSUPPORTED, "No eligible alternative remains", 403)
                config = ranked[0]
            prompt = next(
                p
                for p in policy.prompts
                if stage.prompt and p.id == stage.prompt.id and p.version == stage.prompt.version
            )
            revised = PromptRevision.model_validate(
                prompt.model_dump()
                | {
                    "version": prompt.version + 1,
                    "parent": VersionRef(id=prompt.id, version=prompt.version),
                    "template": request.prompt_templates.get(stage.node_id, prompt.template),
                }
            )
            prompts.append(revised)
            data.update(
                configuration_id=config,
                prompt=VersionRef(id=revised.id, version=revised.version),
                fallback_configuration_ids=(),
            )
            data["budget"] = stage.budget.model_copy(
                update={"max_attempts": 1, "max_model_calls": 1}
            )
            if stage.node_id in request.output_schemas:
                data.update(
                    response_format=ResponseFormat(
                        type="json_schema",
                        json_schema=JsonSchemaFormat(
                            name="result", schema=request.output_schemas[stage.node_id]
                        ),
                    ),
                    output_types={"result": "json"},
                )
            if stage.workload_profile:
                from .intelligence.optimization import assess
                from .routing_contracts import RouterPolicy

                candidate = next(
                    row
                    for row in assess(stage.workload_profile, catalog, RouterPolicy())
                    if row.configuration_id == config
                )
                if not candidate.eligible:
                    raise DomainError(
                        ErrorCode.UNSUPPORTED, "Edited pin violates stage constraints", 403
                    )
        compiled.append(ExecutableStage.model_validate(data))
    return ExecutablePolicy.model_validate(
        policy.model_dump()
        | {
            "version": policy.version + 1,
            "stages": compiled,
            "prompts": prompts,
            "quality": "untested_provisional",
            "variant": None,
            # Manual edits are not a fresh optimizer decision. The preceding exact
            # version retains the original decision; never reuse its winner claim.
            "routing_decision_id": None,
            "router_policy_ref": None,
        }
    )


def variant(
    policy: ExecutablePolicy, catalog: CatalogSnapshot, request: VariantRequest, selector: Selector
) -> ExecutablePolicy:
    if policy.routing_decision_id or any(s.workload_profile for s in policy.stages):
        raise DomainError(
            ErrorCode.UNSUPPORTED,
            "Use workload-intelligence what-if for stage-aware policy variants",
            422,
        )
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
