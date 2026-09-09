"""Central operator provisioning and durable worker records. No raw credentials."""

from pydantic import AwareDatetime, Field

from .contracts import CatalogSnapshot, Identifier
from .execution_contracts import (
    ApplicationKeyMetadata,
    ApprovedEndpoint,
    ExecutionContract,
    ProviderCredentialReference,
    RuntimeGrant,
    SandboxAdmission,
    TargetConfiguration,
)


class SecretReference(ExecutionContract):
    id: Identifier
    environment_name: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,100}$")


class ApprovedBudget(ExecutionContract):
    id: Identifier
    max_cost_micro_usd: int = Field(ge=0, le=1000000, strict=True)


class WorkspaceRuntime(ExecutionContract):
    tenant_id: Identifier
    targets: tuple[TargetConfiguration, ...] = ()
    catalogs: tuple[CatalogSnapshot, ...] = ()
    credentials: tuple[ProviderCredentialReference, ...] = ()
    grants: tuple[RuntimeGrant, ...] = ()
    admissions: tuple[SandboxAdmission, ...] = ()
    endpoints: tuple[ApprovedEndpoint, ...] = ()
    secrets: tuple[SecretReference, ...] = ()
    budgets: tuple[ApprovedBudget, ...] = ()


class RuntimeRegistry(ExecutionContract):
    workspaces: tuple[WorkspaceRuntime, ...] = ()


class QueuedContext(ExecutionContract):
    tenant_id: Identifier
    principal_id: Identifier
    request_id: Identifier
    idempotency_key: Identifier
    deadline: AwareDatetime
    application_key: ApplicationKeyMetadata | None = None
