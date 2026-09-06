"""Bounded research behind frozen CatalogPort/ResearchPort; no worker/API changes."""

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from ..contracts import CatalogSnapshot, Workflow
from ..ports import StoragePort
from .bounds import BoundedReader, BudgetLedger, Limits
from .catalog import SnapshotCatalog, publish
from .evidence import conflicts
from .jobs import (
    ArtifactDiscovery,
    ArtifactInput,
    CapabilityEvidence,
    CapabilityInput,
    DeploymentEvidence,
    DeploymentInput,
    ResearchPlan,
)
from .records import (
    ClaimRecord,
    EndpointRecord,
    FreshnessPolicy,
    Issue,
    ResearchLedger,
    Status,
    failure,
    stable_id,
)
from .sources import RecordedSources


class PublicResearch:
    def __init__(
        self,
        *,
        sources: RecordedSources,
        plan: ResearchPlan,
        storage: StoragePort,
        policy: FreshnessPolicy | None = None,
        limits: Limits | None = None,
        cached: SnapshotCatalog | None = None,
        cancelled: threading.Event | None = None,
    ) -> None:
        self.sources = sources
        self.plan = plan
        self.storage = storage
        self.policy = policy or FreshnessPolicy()
        self.limits = limits or Limits()
        self.cached = cached
        self.cancelled = cancelled if cancelled is not None else threading.Event()
        self.last_budget: BudgetLedger | None = None
        self._lock = threading.Lock()

    def _fresh(self, rows: tuple[ClaimRecord, ...], now: datetime) -> bool:
        if not rows:
            return False
        for row in rows:
            source = self.sources.capture(row.evidence.source_url or "")
            if (
                row.expires_at <= now
                or row.observed_at > now
                or source.digest != row.source_digest
                or source.observed_at != row.observed_at
            ):
                return False
        return True

    def run(self, *, now: datetime | None = None) -> SnapshotCatalog:
        now = now or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("Research time must have a timezone")
        with self._lock:
            budget = BudgetLedger(self.limits)
            self.last_budget = budget
            reader = BoundedReader(self.sources, budget, self.cancelled)
            try:
                reader.check()
                old = (
                    self.cached.ledger()
                    if self.cached
                    else ResearchLedger(freshness_policy=self.policy)
                )
                if old.freshness_policy != self.policy or old.plan_fingerprint != stable_id(
                    "plan", self.plan.cache_key()
                ):
                    old = ResearchLedger(freshness_policy=self.policy)
                cached_artifacts = []
                cached_claims: list[ClaimRecord] = []
                pending_repos = []
                for repo in self.plan.artifacts.repositories:
                    artifact = next((a for a in old.artifacts if a.repository_id == repo), None)
                    rows = tuple(
                        c
                        for c in old.claims
                        if artifact
                        and c.subject_id == artifact.artifact.id
                        and c.field != "capability"
                    )
                    if artifact and self._fresh(rows, now):
                        cached_artifacts.append(artifact)
                        cached_claims.extend(rows)
                    else:
                        pending_repos.append(repo)
                new = (
                    ArtifactDiscovery().run(
                        ArtifactInput(repositories=tuple(pending_repos)), reader, self.policy
                    )
                    if pending_repos
                    else None
                )
                artifacts = tuple(
                    sorted(
                        cached_artifacts + (list(new.artifacts) if new else []),
                        key=lambda a: a.repository_id,
                    )
                )
                claims = cached_claims + (list(new.claims) if new else [])
                issues = list(new.issues) if new else []
                reader.check()
                if any(i.status == Status.BUDGET for i in issues):
                    raise failure(
                        Status.BUDGET, "Artifact discovery exhausted the shared research budget"
                    )
                valid_ids = {a.artifact.id for a in artifacts}
                pending_caps = []
                for spec in self.plan.capabilities:
                    rows = tuple(
                        c
                        for c in old.claims
                        if c.subject_id in valid_ids
                        and c.field == "capability"
                        and c.evidence.source_url == spec.source_url
                        and c.source_locator == spec.source_locator
                    )
                    if self._fresh(rows, now):
                        claims.extend(rows)
                    else:
                        pending_caps.append(spec)
                cached_endpoints: list[EndpointRecord] = []
                pending_deployments = []
                for deployment_spec in self.plan.deployments:
                    eps = tuple(
                        e
                        for e in old.endpoints
                        if e.artifact_id in valid_ids
                        and e.metadata_url == deployment_spec.endpoint_url
                    )
                    endpoint_ids = {e.id for e in eps}
                    rows = tuple(
                        c
                        for c in old.claims
                        if c.subject_kind == "endpoint" and c.subject_id in endpoint_ids
                    )
                    if eps and self._fresh(rows, now):
                        cached_endpoints.extend(eps)
                        claims.extend(rows)
                    else:
                        pending_deployments.append(deployment_spec)
                # Artifact identities are now fixed; the independent roles run concurrently.
                with ThreadPoolExecutor(max_workers=2, thread_name_prefix="research-role") as pool:
                    cap_future = pool.submit(
                        CapabilityEvidence().run,
                        CapabilityInput(artifacts=artifacts, specifications=tuple(pending_caps)),
                        reader,
                        self.policy,
                    )
                    dep_future = pool.submit(
                        DeploymentEvidence().run,
                        DeploymentInput(
                            artifacts=artifacts, specifications=tuple(pending_deployments)
                        ),
                        reader,
                        self.policy,
                    )
                    capability, deployment = cap_future.result(), dep_future.result()
                claims.extend(capability.claims)
                claims.extend(deployment.claims)
                endpoints = tuple(
                    sorted(cached_endpoints + list(deployment.endpoints), key=lambda e: e.id)
                )
                # Recompute coverage across reused and new results, avoiding false gaps on cache hits.
                issues.extend(
                    i for i in capability.issues + deployment.issues if i.status != Status.PARTIAL
                )
                covered_cap = {c.subject_id for c in claims if c.field == "capability"}
                covered_dep = {e.artifact_id for e in endpoints}
                for artifact in artifacts:
                    for covered, label in (
                        (covered_cap, "capability"),
                        (covered_dep, "deployment"),
                    ):
                        if artifact.artifact.id not in covered:
                            issues.append(
                                Issue(
                                    status=Status.PARTIAL,
                                    subject=artifact.artifact.id,
                                    message=f"No validated {label} evidence in this bounded capture; not proof of absence",
                                )
                            )
                reader.check()
                for issue in issues:
                    if issue.status in (Status.CANCELLED, Status.TIMEOUT, Status.BUDGET):
                        raise failure(
                            issue.status,
                            "Research did not complete within its controls; no new snapshot published",
                        )
                rows = tuple(sorted(claims, key=lambda c: c.evidence.id))
                for row in rows:
                    if row.observed_at > now:
                        raise failure(Status.INVALID, "Evidence observation is in the future")
                    if row.expires_at <= now:
                        issues.append(
                            Issue(
                                status=Status.STALE,
                                subject=row.subject_id,
                                message=f"{row.field} evidence expired; replay cannot claim a live refresh",
                            )
                        )
                issues.extend(conflicts(rows))
                ledger = ResearchLedger(
                    freshness_policy=self.policy,
                    plan_fingerprint=stable_id("plan", self.plan.cache_key()),
                    sources=self.sources.captures(),
                    artifacts=artifacts,
                    endpoints=endpoints,
                    claims=rows,
                    issues=tuple(
                        sorted(set_by_json(issues), key=lambda i: (i.subject, i.status, i.message))
                    ),
                    synthetic=all(a.artifact.provenance.kind == "synthetic" for a in artifacts),
                )
                reader.check()
                self.cached = publish(ledger, self.sources, self.plan, self.storage)
                return self.cached
            finally:
                reader.close()

    def snapshot(self) -> CatalogSnapshot:
        return self.run().snapshot()

    def research(self, workflow: Workflow) -> CatalogSnapshot:
        # Deliberately do not serialize/read private title, purpose, input text or tool descriptions.
        # The approved public plan was supplied independently at composition time.
        return self.snapshot()


def set_by_json(issues: list[Issue]) -> tuple[Issue, ...]:
    return tuple({issue.model_dump_json(): issue for issue in issues}.values())
