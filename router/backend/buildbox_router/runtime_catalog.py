"""Read-only exact registry snapshots shared by planning and dispatch; never research."""

from .config import Settings
from .contracts import CatalogSnapshot, ErrorCode
from .errors import DomainError
from .planning_contracts import PlanInput


def catalogs(settings: Settings, tenant: str) -> tuple[CatalogSnapshot, ...]:
    if not settings.runtime_registry_file:
        return ()
    from .execution_composition import load_registry

    rows = [
        w for w in load_registry(settings.runtime_registry_file).workspaces if w.tenant_id == tenant
    ]
    if len(rows) != 1:
        return ()
    return rows[0].catalogs


def planning_catalog(
    settings: Settings, tenant: str, value: PlanInput
) -> tuple[CatalogSnapshot, tuple[str, ...]]:
    rows = [c for c in catalogs(settings, tenant) if c.id == value.runtime_catalog_id]
    if len(rows) != 1 or rows[0].synthetic:
        raise DomainError(
            ErrorCode.UNSUPPORTED,
            "Exact non-synthetic tenant runtime catalog required; no fixture fallback",
            403,
        )
    return rows[0], ()
