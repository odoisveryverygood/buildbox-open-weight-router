"""Tenant/deployment/catalog-scoped circuits; one atomic recovery probe, no model bans."""

import time

from sqlalchemy import text

from ..execution_contracts import CircuitPolicy, FailureKind
from ..execution_storage import SandboxStorage


class DeploymentHealth:
    def __init__(self, store: SandboxStorage):
        self.store = store

    def unavailable(self, tenant: str, catalog: str, now: float | None = None) -> set[str]:
        now = time.time() if now is None else now
        with self.store.engine.connect() as conn:
            return set(
                conn.execute(
                    text(
                        "SELECT configuration_id FROM deployment_health WHERE owner=:o AND catalog_id=:c AND (open_until>:n OR probe_until>:n)"
                    ),
                    {"o": tenant, "c": catalog, "n": now},
                ).scalars()
            )

    def acquire(
        self,
        tenant: str,
        configuration: str,
        catalog: str,
        policy: CircuitPolicy,
        now: float | None = None,
    ) -> bool:
        now = time.time() if now is None else now
        p = {
            "o": tenant,
            "i": configuration,
            "c": catalog,
            "n": now,
            "probe": now + 120,
        }
        with self.store.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO deployment_health(owner,configuration_id,catalog_id,updated_at) VALUES(:o,:i,:c,:n) ON CONFLICT(owner,configuration_id,catalog_id) DO NOTHING"
                ),
                p,
            )
            changed = conn.execute(
                text(
                    "UPDATE deployment_health SET probe_until=CASE WHEN open_until>0 THEN :probe ELSE probe_until END WHERE owner=:o AND configuration_id=:i AND catalog_id=:c AND open_until<=:n AND probe_until<=:n"
                ),
                p,
            )
            return changed.rowcount == 1

    def observe(
        self,
        tenant: str,
        configuration: str,
        catalog: str,
        policy: CircuitPolicy,
        *,
        failure: FailureKind | None,
        latency_ms: int,
        now: float | None = None,
    ) -> None:
        now = time.time() if now is None else now
        # Validation failures describe workload quality, not provider availability.
        unhealthy = failure in ("provider_failure", "rate_limit", "timeout")
        p = {
            "o": tenant,
            "i": configuration,
            "c": catalog,
            "n": now,
            "lat": latency_ms,
            "bad": int(unhealthy),
            "ok": int(failure is None),
            "timeout": int(failure == "timeout"),
            "until": now + policy.cooldown_seconds,
            "threshold": policy.failures,
        }
        with self.store.engine.begin() as conn:
            conn.execute(
                text("""UPDATE deployment_health SET
                total=total+1, successes=successes+:ok, timeouts=timeouts+:timeout,
                latency_total_ms=latency_total_ms+:lat,
                open_until=CASE WHEN :bad=1 AND failures+1>=:threshold THEN :until ELSE 0 END,
                failures=CASE WHEN :bad=1 THEN failures+1 ELSE 0 END,
                probe_until=0, updated_at=:n
                WHERE owner=:o AND configuration_id=:i AND catalog_id=:c"""),
                p,
            )
