"""Existing worker's runtime operation; no second scheduler or private contracts."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from .contracts import ErrorCode
from .errors import DomainError
from .execution_contracts import RunEvent, SandboxRun, WorkflowRunRequest
from .execution_ports import RequestContext
from .execution_security import validate_inputs
from .gateway.runner import WorkflowRunner
from .gateway.service import fingerprint
from .runtime_contracts import QueuedContext


class QueuedWorkflows:
    def __init__(self, runner: WorkflowRunner) -> None:
        self.runner, self.store = runner, runner.store

    async def submit(self, context: RequestContext, value: WorkflowRunRequest) -> SandboxRun:
        policy, _, _ = self.runner.gateway.authority.policy(context, value.policy)
        self.runner._check(context, policy, "workflow:run")
        validate_inputs(policy.input_types, value.inputs)
        identifier = context.request_id
        input_hash = fingerprint(
            "workflow",
            context.principal_id,
            policy.model_dump(mode="json"),
            value.model_dump(mode="json"),
        )
        run = SandboxRun(
            id=identifier,
            policy=value.policy,
            status="queued",
            created_at=datetime.now(UTC),
            quality=policy.quality,
        )
        queued = QueuedContext(
            tenant_id=context.tenant_id,
            principal_id=context.principal_id,
            request_id=identifier,
            idempotency_key=context.idempotency_key,
            deadline=context.deadline,
            application_key=context.application_key,
        )
        identifier, created = self.store.enqueue_runtime(queued, value, run, input_hash)
        if not created:
            return await self.get(context, identifier)
        return run

    async def get(self, context: RequestContext, run_id: str) -> SandboxRun:
        return await self.runner.get(context, run_id)

    async def cancel(self, context: RequestContext, run_id: str) -> SandboxRun:
        return await self.runner.cancel(context, run_id)

    async def events(
        self, context: RequestContext, run_id: str, after_sequence: int
    ) -> AsyncIterator[RunEvent]:
        async for event in self.runner.events(context, run_id, after_sequence):
            yield event

    async def work_once(self) -> bool:
        claimed = self.store.claim_runtime()
        if claimed is None:
            return False
        queued, value = claimed

        def check() -> None:
            if datetime.now(UTC) >= queued.deadline or self.store.request_state(
                queued.tenant_id, queued.request_id
            ) not in ("queued", "running"):
                raise DomainError(ErrorCode.UNSUPPORTED, "Queued run cancelled/expired", 408)

        key = queued.application_key
        if key:
            key, _ = self.store.key_record(queued.tenant_id, key.id)
        context = RequestContext(
            queued.tenant_id,
            queued.principal_id,
            queued.request_id,
            queued.idempotency_key,
            queued.deadline,
            check,
            key,
        )
        try:
            await self.runner.submit(context, value, worker_claimed=True)
            self.store.finish_runtime(queued.tenant_id, queued.request_id)
        except Exception:
            self.store.finish_runtime(queued.tenant_id, queued.request_id, uncertain=True)
        return True
