"""Content-free terminal observations. Never promoted to model-quality evidence."""

from ..execution_contracts import SandboxRun
from ..execution_storage import SandboxStorage, append
from ..routing_contracts import ExecutionOutcome, OutcomeRating


def record_outcome(store: SandboxStorage, tenant: str, run: SandboxRun) -> None:
    attempts = store.attempts(tenant, run.id)
    policy = store.policy(tenant, run.policy).policy
    final_by_node = {a.node_id: a for a in sorted(attempts, key=lambda a: a.attempt)}
    final_validation = [v for a in final_by_node.values() for v in a.validation]
    outcome = ExecutionOutcome(
        run_id=run.id,
        policy=run.policy,
        catalog_id=policy.catalog_id,
        decision_id=policy.routing_decision_id,
        status=run.status,
        validation_passed=all(v.passed for v in final_validation) if final_validation else None,
        failed_validations=sum(not v.passed for a in attempts for v in a.validation),
        attempt_count=len(attempts),
        attempt_latency_ms=sum(a.latency_ms for a in attempts if a.latency_ms is not None)
        if attempts and all(a.latency_ms is not None for a in attempts)
        else None,
        known_cost_micro_usd=sum(
            a.usage.actual_micro_usd for a in attempts if a.usage.actual_micro_usd is not None
        ),
        unknown_cost_attempts=sum(a.usage.actual_micro_usd is None for a in attempts),
        fallback_count=sum(a.recovery_action == "fallback" for a in attempts),
        repair_count=sum(a.recovery_action == "repair" for a in attempts),
        synthetic=store.offline_contract_test,
    )
    with store.engine.begin() as conn:
        append(conn, tenant, "execution_outcome", run.id, 1, outcome)


def history(store: SandboxStorage, tenant: str) -> tuple[ExecutionOutcome, ...]:
    outcomes = [
        ExecutionOutcome.model_validate_json(r) for r in store.records(tenant, "execution_outcome")
    ]
    result = []
    for value in outcomes:
        from ..errors import DomainError

        try:
            rating = OutcomeRating.model_validate_json(
                store.read(tenant, "outcome_rating", value.run_id)
            )
            value = value.model_copy(update={"rating": rating.rating})
        except DomainError:
            pass
        result.append(value)
    return tuple(result)
