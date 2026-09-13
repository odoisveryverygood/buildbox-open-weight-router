"""Central product/worker composition of the preserved runtime implementations."""

import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue
from sqlalchemy.exc import IntegrityError

from .config import Settings
from .contracts import CatalogSnapshot, ErrorCode
from .errors import DomainError
from .execution_comparisons import Comparisons
from .execution_contracts import (
    ApprovedEndpoint,
    ProviderCredentialReference,
    RuntimeGrant,
    TargetConfiguration,
)
from .execution_jobs import QueuedWorkflows
from .execution_ports import ExecutionServices
from .execution_storage import SandboxStorage, append
from .gateway.adapters import TargetAdapters
from .gateway.keys import ApplicationKeys
from .gateway.preflight import Authority
from .gateway.runner import SampleTools, WorkflowRunner
from .gateway.service import Gateway
from .ports import Selector
from .runtime_contracts import RuntimeRegistry, WorkspaceRuntime


def load_registry(path: str) -> RuntimeRegistry:
    raw = Path(path).read_bytes()
    if len(raw) > 2000000:
        raise ValueError("Runtime registry exceeds bound")
    return RuntimeRegistry.model_validate_json(raw)


def compose_execution(
    store: SandboxStorage,
    registry: RuntimeRegistry,
    selector: Selector,
    *,
    retention_seconds: int,
    registry_loader: Callable[[], RuntimeRegistry] | None = None,
) -> ExecutionServices:
    def workspace(tenant: str) -> WorkspaceRuntime:
        current = registry_loader() if registry_loader else registry
        values = [w for w in current.workspaces if w.tenant_id == tenant]
        if len(values) != 1:
            raise DomainError(ErrorCode.UNSUPPORTED, "No approved runtime workspace", 403)
        return values[0]

    def target(tenant: str, identifier: str) -> TargetConfiguration:
        values = [v for v in workspace(tenant).targets if v.configuration.id == identifier]
        if len(values) != 1:
            raise DomainError(ErrorCode.UNSUPPORTED, "Approved target unavailable", 403)
        return values[0]

    def catalog(tenant: str, identifier: str) -> CatalogSnapshot:
        values = [v for v in workspace(tenant).catalogs if v.id == identifier]
        if len(values) != 1:
            raise DomainError(ErrorCode.UNSUPPORTED, "Approved catalog unavailable", 403)
        return values[0]

    def grant(tenant: str, identifier: str) -> RuntimeGrant:
        values = [v for v in workspace(tenant).grants if identifier in v.configuration_ids]
        if len(values) != 1:
            raise DomainError(ErrorCode.UNSUPPORTED, "Exact runtime grant unavailable", 403)
        return values[0]

    def credential(tenant: str, identifier: str) -> ProviderCredentialReference:
        values = [
            v for v in workspace(tenant).credentials if v.id == identifier and v.tenant_id == tenant
        ]
        if len(values) != 1:
            raise DomainError(ErrorCode.UNSUPPORTED, "Scoped provider credential unavailable", 403)
        return values[0]

    def endpoint(tenant: str, identifier: str) -> ApprovedEndpoint:
        values = [
            v for v in workspace(tenant).endpoints if v.id == identifier and v.tenant_id == tenant
        ]
        if len(values) != 1:
            raise DomainError(ErrorCode.UNSUPPORTED, "Scoped endpoint unavailable", 403)
        return values[0]

    def secret(tenant: str, identifier: str) -> str:
        values = [v for v in workspace(tenant).secrets if v.id == identifier]
        if len(values) != 1:
            raise DomainError(ErrorCode.UNSUPPORTED, "Approved secret binding unavailable", 403)
        value = os.getenv(values[0].environment_name)
        if not value:
            raise DomainError(
                ErrorCode.UNSUPPORTED, "Approved server secret is not configured", 403
            )
        return value

    def packet(tenant: str, tool_id: str) -> dict[str, JsonValue]:
        values = [
            p
            for p in workspace(tenant).read_only_packets
            if p.tool_id == tool_id and p.observed_at <= datetime.now(UTC) < p.expires_at
        ]
        if len(values) != 1:
            raise DomainError(ErrorCode.UNSUPPORTED, "Current read-only packet unavailable", 403)
        return values[0].rows

    # Registry is administrator-supplied, never accepted from browser/model output.
    for item in registry.workspaces:
        for budget in item.budgets:
            try:
                store.provision_budget(item.tenant_id, budget.id, budget.max_cost_micro_usd)
            except IntegrityError:
                if store.budget_cap(item.tenant_id, budget.id) != budget.max_cost_micro_usd:
                    raise ValueError(
                        "Registry cannot silently replace an existing immutable budget cap"
                    ) from None
        with store.engine.begin() as conn:
            for admission in item.admissions:
                if admission.tenant_id != item.tenant_id:
                    raise ValueError("Admission registry ownership mismatch")
                append(conn, item.tenant_id, "admission", admission.id, 1, admission)
    authority = Authority(
        store,
        target=target,
        grant=grant,
        credential=credential,
        catalog=catalog,
        selector=selector,
        local_egress=lambda tenant, target: (
            bool(target.local)
            or bool(
                target.approved_endpoint_id
                and endpoint(tenant, target.approved_endpoint_id).network == "loopback"
            )
        ),
    )
    keys = ApplicationKeys(store)
    gateway = Gateway(
        authority,
        TargetAdapters(secret, endpoint),
        keys,
        streaming_enabled=True,
        repair_retain_seconds=retention_seconds,
    )
    workflows = QueuedWorkflows(
        WorkflowRunner(
            gateway,
            SampleTools(
                {
                    (w.tenant_id, p.tool_id): p.rows
                    for w in registry.workspaces
                    for p in w.read_only_packets
                    if p.observed_at <= datetime.now(UTC) < p.expires_at
                },
                expires={
                    (w.tenant_id, p.tool_id): p.expires_at
                    for w in registry.workspaces
                    for p in w.read_only_packets
                },
                current=packet,
            ),
            retain_seconds=retention_seconds,
        )
    )
    return ExecutionServices(gateway, workflows, keys, Comparisons(workflows))


def configured_execution(
    settings: Settings, store: SandboxStorage, selector: Selector
) -> ExecutionServices | None:
    if settings.runtime_registry_file is None:
        return None  # Explicitly unavailable, never automatic fixture inference.
    if settings.identity_mode != "shared" or settings.mode != "live":
        raise ValueError("Configured target runtime requires authenticated shared identity")
    return compose_execution(
        store,
        load_registry(settings.runtime_registry_file),
        selector,
        retention_seconds=settings.runtime_retention_seconds,
        registry_loader=lambda: load_registry(settings.runtime_registry_file or ""),
    )
