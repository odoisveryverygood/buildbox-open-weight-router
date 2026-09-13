"""Workload intelligence API; no public catalog upload, grants or hidden execution."""

from uuid import uuid4

from fastapi import APIRouter, Request
from sqlalchemy import text

from . import routing_service as service
from .contracts import CatalogSnapshot, ErrorCode, WorkloadProfile
from .errors import DomainError
from .execution_api import repository
from .execution_contracts import ExecutablePolicy
from .execution_storage import append
from .intelligence.workload import analyze
from .planning_contracts import PlanningResult
from .routing_contracts import (
    AdvancedStatus,
    CatalogChange,
    CatalogDiffRequest,
    DraftFromDecision,
    ExecutionOutcome,
    OutcomeRating,
    PolicyEvaluationReport,
    PolicyEvaluationRequest,
    PreviewRequest,
    RouterMetrics,
    RoutingDecision,
    ShadowComparison,
    WhatIfRequest,
    WorkloadRequest,
)

router = APIRouter(prefix="/api/studio/intelligence", tags=["Workload intelligence"])


@router.get("/outcomes")
def outcomes(request: Request) -> tuple[ExecutionOutcome, ...]:
    from .gateway.outcomes import history

    return history(repository(request), request.state.owner)


@router.post("/outcomes/{identifier}/rating")
def rate_outcome(identifier: str, value: OutcomeRating, request: Request) -> OutcomeRating:
    store, owner = repository(request), request.state.owner
    store.read(owner, "execution_outcome", identifier)
    with store.engine.begin() as conn:
        # One explicit immutable rating per outcome; cannot manufacture a sample count.
        append(conn, owner, "outcome_rating", identifier, 1, value)
    return value


def catalogs(request: Request) -> dict[str, CatalogSnapshot]:
    owner = request.state.owner
    store = repository(request)
    # Explicit software-test injection is scoped and unavailable in normal mode.
    injected = getattr(request.app.state, "intelligence_catalogs", {})
    result = dict(injected.get(owner, {})) if store.offline_contract_test else {}
    with store.engine.connect() as conn:
        rows = conn.execute(
            text("SELECT payload FROM records WHERE owner=:o AND kind='planning_result' LIMIT 100"),
            {"o": owner},
        ).scalars()
        for raw in rows:
            value = PlanningResult.model_validate_json(raw)
            if value.catalog:
                old = result.get(value.catalog.id)
                if old is not None and old != value.catalog:
                    raise DomainError(
                        ErrorCode.CONFLICT, "Catalog ID resolves to conflicting content", 409
                    )
                result[value.catalog.id] = value.catalog
    config = request.app.state.runtime_config
    if config.runtime_registry_file:
        from .execution_composition import load_registry

        for workspace in load_registry(config.runtime_registry_file).workspaces:
            if workspace.tenant_id == owner:
                for catalog in workspace.catalogs:
                    if catalog.id in result and result[catalog.id] != catalog:
                        raise DomainError(ErrorCode.CONFLICT, "Runtime catalog content drift", 409)
                    result[catalog.id] = catalog
    return result


def catalog(request: Request, identifier: str) -> CatalogSnapshot:
    value = catalogs(request).get(identifier)
    if value is None:
        raise DomainError(ErrorCode.NOT_FOUND, "Owned catalog snapshot not found", 404)
    return value


@router.get("/status")
def status(request: Request) -> AdvancedStatus:
    store = repository(request)
    scenarios = (
        getattr(request.app.state, "advanced_scenarios", ())
        if store.offline_contract_test and request.state.owner == "alice"
        else ()
    )
    return AdvancedStatus(
        catalog_ids=tuple(catalogs(request)),
        scenarios=scenarios,
        synthetic=store.offline_contract_test,
    )


@router.post("/analyze")
def analyze_workload(value: WorkloadRequest) -> WorkloadProfile:
    return analyze(value)


@router.post("/preview")
def preview(value: PreviewRequest, request: Request) -> RoutingDecision:
    return service.preview(
        repository(request), request.state.owner, value, catalog(request, value.catalog_id)
    )


@router.get("/decisions/{identifier}")
def get_decision(identifier: str, request: Request) -> RoutingDecision:
    return service.decision(repository(request), request.state.owner, identifier)


@router.post("/decisions/{identifier}/what-if")
def what_if(identifier: str, value: WhatIfRequest, request: Request) -> RoutingDecision:
    store, owner = repository(request), request.state.owner
    return service.what_if(store, owner, service.decision(store, owner, identifier), value)[0]


@router.post("/decisions/{identifier}/shadow")
def shadow(identifier: str, value: WhatIfRequest, request: Request) -> ShadowComparison:
    store, owner = repository(request), request.state.owner
    return service.what_if(store, owner, service.decision(store, owner, identifier), value)[1]


@router.post("/drafts", status_code=201)
def draft(value: DraftFromDecision, request: Request) -> ExecutablePolicy:
    store = repository(request)
    return service.draft(
        store, request.state.owner, service.decision(store, request.state.owner, value.decision_id)
    )


@router.post("/catalog-diff")
def diff(value: CatalogDiffRequest, request: Request) -> tuple[CatalogChange, ...]:
    return service.catalog_diff(catalog(request, value.before), catalog(request, value.after))


@router.get("/metrics")
def metrics(request: Request) -> RouterMetrics:
    return service.metrics(repository(request), request.state.owner)


@router.post("/evaluate")
def evaluate(value: PolicyEvaluationRequest, request: Request) -> PolicyEvaluationReport:
    store, owner = repository(request), request.state.owner
    comparisons = tuple(
        service.what_if(
            store,
            owner,
            service.decision(store, owner, identifier),
            WhatIfRequest(policy=value.experimental),
        )[1]
        for identifier in value.decisions
    )
    result = PolicyEvaluationReport(
        id=uuid4().hex,
        comparisons=comparisons,
        case_count=len(comparisons),
        disagreement_rate=sum(bool(c.disagreements) for c in comparisons) / len(comparisons),
    )
    with store.engine.begin() as conn:
        append(conn, owner, "router_evaluation", result.id, 1, result)
    return result
