"""Validate and publish immutable catalog projections using shared storage/records."""

import json
from datetime import datetime

from pydantic import ValidationError

from ..contracts import (
    CandidateConfiguration,
    CatalogSnapshot,
    ErrorCode,
    Evidence,
    Fact,
    Provenance,
)
from ..errors import DomainError
from ..ports import StoragePort
from .jobs import ResearchPlan, capability_claim
from .normalizers import artifact_from_hub, endpoints_from_openrouter
from .records import EndpointRecord, Record, ResearchLedger, Status, failure, stable_id
from .sources import RecordedSources

PUBLIC_OWNER = "public-research-snapshot"  # Storage namespace, never authentication.


class ConfigurationBinding(Record):
    endpoint_id: str
    prompt_template_ref: str
    harness_ref: str


def configuration(
    endpoint: EndpointRecord, binding: ConfigurationBinding
) -> CandidateConfiguration:
    p = endpoint.provider.provenance
    return CandidateConfiguration(
        id=stable_id("config", endpoint.id, binding.prompt_template_ref, binding.harness_ref),
        artifact_id=endpoint.artifact_id,
        provider=endpoint.provider,
        region=endpoint.region,
        quantization=endpoint.quantization,
        hardware=endpoint.hardware,
        prompt_template_ref=binding.prompt_template_ref,
        harness_ref=binding.harness_ref,
        reasoning_budget=Fact[int](
            provenance=p, unknown_reason="No tested reasoning configuration"
        ),
        cost_per_1k_tokens=Fact[float](
            provenance=p,
            unknown_reason="Separate input/output/other price units cannot become one workload cost without an explicit usage mix",
        ),
        latency_ms=Fact[float](provenance=p, unknown_reason="No workload latency test performed"),
        provenance=Provenance(kind=p.kind, source=p.source, evidence_ids=endpoint.evidence_ids),
    )


def validate_ledger(ledger: ResearchLedger, sources: RecordedSources, plan: ResearchPlan) -> None:
    try:
        ResearchLedger.model_validate_json(ledger.model_dump_json())
    except ValidationError:
        raise failure(Status.INVALID, "Research record schema validation failed") from None
    if ledger.plan_fingerprint != stable_id("plan", plan.cache_key()):
        raise failure(Status.INVALID, "Research plan fingerprint mismatch")
    if ledger.sources != sources.captures():
        raise failure(Status.INVALID, "Retained public source snapshot mismatch")
    artifacts = {a.artifact.id: a for a in ledger.artifacts}
    endpoints = {e.id: e for e in ledger.endpoints}
    claims = {c.evidence.id: c for c in ledger.claims}
    validated_ids: set[str] = set()
    if (
        len(artifacts) != len(ledger.artifacts)
        or len(endpoints) != len(ledger.endpoints)
        or len(claims) != len(ledger.claims)
    ):
        raise failure(Status.CONFLICT, "Duplicate research identifier")
    if not artifacts:
        raise failure(
            Status.PARTIAL,
            "No validated artifacts in the bounded evidence snapshot; eligibility remains unknown",
        )
    for artifact in ledger.artifacts:
        source = sources.capture(f"https://huggingface.co/api/models/{artifact.repository_id}")
        expected, rows = artifact_from_hub(artifact.repository_id, source, ledger.freshness_policy)
        validated_ids.update(row.evidence.id for row in rows)
        if artifact != expected or any(claims.get(row.evidence.id) != row for row in rows):
            raise failure(
                Status.INVALID, "Artifact proposal differs from deterministic source validation"
            )
    for endpoint in ledger.endpoints:
        endpoint_artifact = artifacts.get(endpoint.artifact_id)
        if endpoint_artifact is None:
            raise failure(Status.INVALID, "Endpoint references an unknown artifact")
        spec = next(
            (
                s
                for s in plan.deployments
                if s.repository == endpoint_artifact.repository_id
                and s.endpoint_url == endpoint.metadata_url
            ),
            None,
        )
        if spec is None:
            raise failure(Status.INVALID, "Endpoint is outside the approved public source plan")
        expected_endpoints, expected_claims = endpoints_from_openrouter(
            endpoint_artifact,
            sources.capture(spec.model_url),
            sources.capture(spec.endpoint_url),
            ledger.freshness_policy,
        )
        validated_ids.update(c.evidence.id for c in expected_claims)
        if endpoint not in expected_endpoints or any(
            claims.get(c.evidence.id) != c for c in expected_claims
        ):
            raise failure(
                Status.INVALID, "Endpoint proposal differs from deterministic source validation"
            )
    for row in ledger.claims:
        source = sources.capture(row.evidence.source_url or "")
        if source.synthetic != ledger.synthetic or row.evidence.provenance.kind != (
            "synthetic" if ledger.synthetic else "documented"
        ):
            raise failure(Status.INVALID, "Public and synthetic evidence cannot be mixed")
        if (
            source.id != row.source_id
            or source.digest != row.source_digest
            or source.observed_at != row.observed_at
        ):
            raise failure(Status.INVALID, "Evidence source/provenance mismatch")
        if row.expires_at != ledger.freshness_policy.expiry(row.field, row.observed_at):
            raise failure(Status.INVALID, "Evidence expiry differs from configured field policy")
        if row.subject_id not in (artifacts if row.subject_kind == "artifact" else endpoints):
            raise failure(Status.INVALID, "Evidence subject does not exist")
        if row.field == "capability":
            artifact = artifacts[row.subject_id]
            cap_spec = next(
                (
                    s
                    for s in plan.capabilities
                    if s.repository == artifact.repository_id
                    and s.source_url == source.url
                    and s.source_locator == row.source_locator
                ),
                None,
            )
            if (
                cap_spec is None
                or capability_claim(source, cap_spec, artifact, ledger.freshness_policy) != row
            ):
                raise failure(
                    Status.INVALID, "Capability proposal lacks an exact validated table cell"
                )
        elif row.evidence.id not in validated_ids:
            raise failure(
                Status.INVALID, "Claim was not produced by deterministic source validation"
            )


class SnapshotCatalog:
    """Pinned CatalogPort. No mutable head is consulted after recommendation freeze."""

    def __init__(self, storage: StoragePort, snapshot_id: str) -> None:
        self.storage = storage
        self.snapshot_id = snapshot_id

    def snapshot(self) -> CatalogSnapshot:
        payload = self.storage.get(PUBLIC_OWNER, "public_catalog", self.snapshot_id)
        return CatalogSnapshot.model_validate_json(payload)

    def ledger(self) -> ResearchLedger:
        return ResearchLedger.model_validate_json(
            self.storage.get(PUBLIC_OWNER, "research_ledger", self.snapshot_id)
        )


def publish(
    ledger: ResearchLedger,
    sources: RecordedSources,
    plan: ResearchPlan,
    storage: StoragePort,
    bindings: tuple[ConfigurationBinding, ...] = (),
) -> SnapshotCatalog:
    validate_ledger(ledger, sources, plan)
    by_id = {endpoint.id: endpoint for endpoint in ledger.endpoints}
    configs = []
    for binding in bindings:
        endpoint = by_id.get(binding.endpoint_id)
        if endpoint is None:
            raise failure(Status.INVALID, "Configuration binding references an unknown endpoint")
        artifact = next(a for a in ledger.artifacts if a.artifact.id == endpoint.artifact_id)
        if artifact.artifact.license.value is None or not (artifact.access.value or "").startswith(
            "public"
        ):
            raise failure(
                Status.PARTIAL,
                "License/access clearance cannot be represented safely in v1 configuration",
            )
        configs.append(configuration(endpoint, binding))
    ledger_json = ledger.canonical_json()
    snapshot_id = stable_id(
        "catalog", ledger_json, json.dumps([b.model_dump() for b in bindings], sort_keys=True)
    )
    provenance = Provenance(
        kind="synthetic" if ledger.synthetic else "documented",
        source="Validated lane research ledger",
    )
    summary = Evidence(
        id=stable_id("coverage", snapshot_id),
        title="Research coverage and immutable ledger reference",
        claim=f"Ledger {snapshot_id}; {len(ledger.artifacts)} artifacts, {len(ledger.endpoints)} endpoint declarations, {len(configs)} bound configurations. Statuses: {', '.join(sorted({i.status.value for i in ledger.issues})) or 'complete'}. Endpoint declarations are not tested configurations; no model-quality validation.",
        captured_at=max(c.observed_at for c in ledger.claims).isoformat(),
        provenance=provenance,
    )
    snapshot = CatalogSnapshot(
        id=snapshot_id,
        artifacts=tuple(a.artifact for a in ledger.artifacts),
        configurations=tuple(configs),
        evidence=tuple(c.evidence for c in ledger.claims) + (summary,),
        synthetic=ledger.synthetic,
    )
    # Shared port has no multi-object transaction. Ledger first: a crash can leave
    # an orphan ledger, but cannot expose a catalog without its rich evidence.
    put_once(storage, "research_ledger", snapshot_id, ledger_json)
    put_once(storage, "public_catalog", snapshot_id, snapshot.model_dump_json())
    return SnapshotCatalog(storage, snapshot_id)


def put_once(storage: StoragePort, kind: str, object_id: str, payload: str) -> None:
    try:
        storage.put(PUBLIC_OWNER, kind, object_id, payload)
    except DomainError as exc:
        if exc.detail.code != ErrorCode.CONFLICT:
            raise
        if storage.get(PUBLIC_OWNER, kind, object_id) != payload:
            raise failure(Status.CONFLICT, "Immutable public snapshot payload differs") from None


def stale_issues(ledger: ResearchLedger, now: datetime) -> tuple[str, ...]:
    return tuple(row.evidence.id for row in ledger.claims if row.expires_at <= now)
