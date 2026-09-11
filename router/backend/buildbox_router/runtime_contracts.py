"""Central operator provisioning and durable worker records. No raw credentials."""

from pydantic import AwareDatetime, Field, JsonValue, model_validator

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


class ReadOnlyPacket(ExecutionContract):
    tool_id: str = Field(pattern=r"^sample-lookup-[A-Za-z0-9_-]{1,50}$")
    rows: dict[str, JsonValue] = Field(repr=False)
    source_label: str = Field(min_length=1, max_length=200)
    provenance: str = Field(min_length=1, max_length=2000)
    data_class: str = Field(pattern=r"^(synthetic|public_excerpt)$")
    observed_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def bounded(self) -> "ReadOnlyPacket":
        if (
            len(self.rows) > 100
            or len(self.model_dump_json().encode()) > 65536
            or self.expires_at <= self.observed_at
        ):
            raise ValueError("Packet exceeds bounds or has invalid retention")
        return self


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
    read_only_packets: tuple[ReadOnlyPacket, ...] = ()


class RuntimeRegistry(ExecutionContract):
    workspaces: tuple[WorkspaceRuntime, ...] = ()


class QueuedContext(ExecutionContract):
    tenant_id: Identifier
    principal_id: Identifier
    request_id: Identifier
    idempotency_key: Identifier
    deadline: AwareDatetime
    application_key: ApplicationKeyMetadata | None = None
