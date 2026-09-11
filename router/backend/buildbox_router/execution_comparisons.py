"""Exploratory comparison over the same worker-run path, not fabricated outputs."""

from dataclasses import replace

from .contracts import ErrorCode
from .errors import DomainError
from .execution_contracts import (
    ComparisonCell,
    ComparisonRequest,
    ComparisonResult,
    WorkflowRunRequest,
)
from .execution_jobs import QueuedWorkflows
from .execution_ports import RequestContext
from .execution_security import validate_inputs
from .gateway.service import fingerprint


class Comparisons:
    def __init__(self, workflows: QueuedWorkflows) -> None:
        self.workflows, self.store = workflows, workflows.store

    async def submit(self, context: RequestContext, value: ComparisonRequest) -> ComparisonResult:
        policies = [
            self.workflows.runner.gateway.authority.policy(context, p)[0] for p in value.policies
        ]
        for p in policies:
            self.workflows.runner._check(context, p, "workflow:run")
            for sample_id in value.sample_ids:
                sample = self.store.sample(context.tenant_id, sample_id)
                validate_inputs(p.input_types, sample.inputs)
        for field in ("max_cost_micro_usd", "max_model_calls", "max_tool_calls"):
            if sum(getattr(p.budget, field) for p in policies) * len(value.sample_ids) > getattr(
                value.budget, field
            ):
                raise DomainError(
                    ErrorCode.UNSUPPORTED,
                    "Comparison aggregate envelope exceeds approved request cap",
                    429,
                )
        identifier, created = self.store.register_request(
            context.tenant_id,
            context.idempotency_key,
            context.request_id,
            fingerprint("comparison", context.principal_id, value.model_dump(mode="json")),
        )
        if not created:
            return await self.get(context, identifier)
        cells = [
            ComparisonCell(
                sample_id=sample_id,
                policy=ref,
                run_id=fingerprint(identifier, ref.id, ref.version, sample_id)[:32],
                status="not_run",
            )
            for ref in value.policies
            for sample_id in value.sample_ids
        ]
        result = ComparisonResult(id=identifier, request=value, cells=tuple(cells))
        # Persist every child ID BEFORE any queue admission. A crash can leave a
        # blocked cell, never an untracked costed child or an automatic replay.
        self.store.save_comparison(context.tenant_id, result, 1)
        for policy in policies:
            for sample_id in value.sample_ids:
                sample = self.store.sample(context.tenant_id, sample_id)
                child_id = fingerprint(identifier, policy.id, policy.version, sample_id)[:32]
                await self.workflows.submit(
                    replace(context, request_id=child_id, idempotency_key=child_id),
                    WorkflowRunRequest(
                        policy=next(
                            p
                            for p in value.policies
                            if p.id == policy.id and p.version == policy.version
                        ),
                        inputs=sample.inputs,
                        sample_reference=sample_id,
                    ),
                )
        return result

    async def get(self, context: RequestContext, comparison_id: str) -> ComparisonResult:
        revision, raw = self.store.latest(context.tenant_id, "comparison", comparison_id)
        saved = ComparisonResult.model_validate_json(raw)
        cells = []
        for cell in saved.cells:
            if cell.run_id is None:
                cells.append(cell)
                continue
            try:
                run = await self.workflows.get(context, cell.run_id)
            except DomainError as error:
                if error.status != 404:
                    raise
                cells.append(cell.model_copy(update={"status": "blocked"}))
                continue
            records = [v.usage for v in self.store.attempts(context.tenant_id, run.id)]
            state = (
                "completed"
                if run.status == "succeeded" and run.output_reference and records
                else "failed"
                if run.status in ("failed", "uncertain", "cancelled")
                else "blocked"
                if run.status == "awaiting_approval"
                else "not_run"
            )
            cells.append(
                ComparisonCell.model_validate(
                    cell.model_dump()
                    | {
                        "status": state,
                        "output_reference": run.output_reference,
                        "attempt_usages": records,
                    }
                )
            )
        result = saved.model_copy(update={"cells": tuple(cells)})
        # Do not append timestamp-only changes forever on read; persist only state/ref changes.
        if result != saved:
            self.store.save_comparison(context.tenant_id, result, revision + 1)
        return result
