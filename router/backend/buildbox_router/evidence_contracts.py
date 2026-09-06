"""Canonical research evidence contracts promoted by integration; legacy records re-export these."""

import hashlib
import json
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from .contracts import Evidence, Fact, ModelArtifact, Provenance


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Status(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial_coverage"
    INACCESSIBLE = "inaccessible"
    CONFLICT = "source_conflict"
    STALE = "stale_data"
    BUDGET = "budget_exhausted"
    SEARCH_LIMIT = "search_limit"
    RATE_LIMIT = "rate_limited"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNSAFE = "unsafe_source"
    INVALID = "invalid_evidence"
    UNAVAILABLE = "runtime_unavailable"


class Issue(Record):
    status: Status
    subject: str
    message: str
    retryable: bool = False


class ResearchFailure(Exception):
    def __init__(self, issue: Issue) -> None:
        super().__init__(issue.message)
        self.issue = issue


def failure(status: Status, message: str, subject: str = "research") -> ResearchFailure:
    return ResearchFailure(Issue(status=status, subject=subject, message=message))


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(json.dumps(parts, ensure_ascii=True).encode()).hexdigest()[:40]
    return f"{prefix}-{digest}"


def unknown[T](kind: type[T], provenance: Provenance, reason: str) -> Fact[T]:
    return Fact[T](provenance=provenance, unknown_reason=reason)


SourceType = Literal["publisher_metadata", "publisher_card", "official_endpoint", "benchmark"]


class SourceCapture(Record):
    id: str
    url: str
    source_type: SourceType
    observed_at: AwareDatetime
    body: str = Field(repr=False, max_length=1_048_576)
    synthetic: bool = False
    retention: str = "Minimal public fields/excerpts, not a complete source document"

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.body.encode()).hexdigest()


class FreshnessPolicy(Record):
    """Configurable engineering defaults, not claims about universal shelf life."""

    version: str = "freshness-1"
    identity_seconds: int = Field(default=2_592_000, ge=1)
    license_seconds: int = Field(default=604_800, ge=1)
    access_seconds: int = Field(default=86_400, ge=1)
    capability_seconds: int = Field(default=2_592_000, ge=1)
    deployment_seconds: int = Field(default=86_400, ge=1)
    pricing_seconds: int = Field(default=21_600, ge=1)

    def expiry(self, field: str, observed_at: datetime) -> datetime:
        ttl = {
            "identity": self.identity_seconds,
            "license": self.license_seconds,
            "access": self.access_seconds,
            "capability": self.capability_seconds,
            "deployment": self.deployment_seconds,
            "pricing": self.pricing_seconds,
        }[field]
        return observed_at + timedelta(seconds=ttl)


class ClaimRecord(Record):
    evidence: Evidence
    subject_id: str
    subject_kind: Literal["artifact", "endpoint"]
    field: Literal["identity", "license", "access", "capability", "deployment", "pricing"]
    source_id: str
    source_type: SourceType
    source_locator: str = Field(min_length=1)
    source_digest: str
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    publication_date: Fact[str]
    tested_at: Fact[str]
    raw_metric: Fact[str]
    metric_unit: Fact[str]
    benchmark_name: Fact[str]
    benchmark_version: Fact[str]
    benchmark_split: Fact[str]
    harness: Fact[str]
    settings: Fact[str]
    sample_size: Fact[int]
    limitations: tuple[str, ...] = Field(min_length=1)
    measured_by_us: Literal[False] = False

    @model_validator(mode="after")
    def chronological(self) -> "ClaimRecord":
        if self.expires_at <= self.observed_at:
            raise ValueError("Evidence expiry must follow observation")
        return self


class ArtifactRecord(Record):
    artifact: ModelArtifact
    repository_id: str
    repository_url: str
    publisher: Fact[str]
    weight_files: tuple[str, ...]
    access: Fact[str]
    license_url: Fact[str]
    license_terms_reviewed: Literal[False] = False
    declared_task: Fact[str]
    input_modalities: Fact[tuple[str, ...]]
    output_modalities: Fact[tuple[str, ...]]
    release_date: Fact[str]
    identity_claim_id: str


class PriceComponent(Record):
    component: str
    raw_amount: str
    currency: Literal["USD", "unknown"] = "USD"
    unit: Literal["token", "request", "image", "search", "unknown"]
    usd_per_million_tokens: str | None = None

    @model_validator(mode="after")
    def finite_price(self) -> "PriceComponent":
        if self.unit == "unknown" and self.currency != "unknown":
            raise ValueError("Unrecognized components cannot assert a currency")
        amount = Decimal(self.raw_amount)
        if not amount.is_finite() or amount < 0:
            raise ValueError("Price must be finite and nonnegative")
        expected = str(amount * 1_000_000) if self.unit == "token" else None
        if self.usd_per_million_tokens != expected:
            raise ValueError("Price unit conversion mismatch")
        return self


class EndpointRecord(Record):
    id: str
    artifact_id: str
    routing_model_id: str
    endpoint_tag: str
    provider: Fact[str]
    deployment_mode: Literal["hosted_gateway"] = "hosted_gateway"
    metadata_url: str
    serving_url: Fact[str]
    served_revision: Fact[str]
    supported_parameters: Fact[tuple[str, ...]]
    context_tokens: Fact[int]
    max_prompt_tokens: Fact[int]
    max_completion_tokens: Fact[int]
    quantization: Fact[str]
    hardware: Fact[str]
    region: Fact[str]
    privacy: Fact[str]
    provider_restrictions: Fact[str]
    prices: tuple[PriceComponent, ...]
    conditional_pricing: Fact[str]
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def effective_output_limit(self, input_tokens: int) -> int | None:
        if input_tokens < 0:
            raise ValueError("Input token count cannot be negative")
        context = self.context_tokens.value
        output = self.max_completion_tokens.value
        prompt = self.max_prompt_tokens.value
        if context is None or output is None or prompt is None:
            return None
        if input_tokens > prompt or input_tokens >= context:
            return 0
        return min(output, context - input_tokens)


class ResearchLedger(Record):
    format_version: Literal["research-ledger-1"] = "research-ledger-1"
    freshness_policy: FreshnessPolicy
    plan_fingerprint: str = "unplanned"
    parser_versions: tuple[str, ...] = (
        "artifact-discovery-1",
        "capability-evidence-1",
        "deployment-evidence-1",
    )
    sources: tuple[SourceCapture, ...] = ()
    artifacts: tuple[ArtifactRecord, ...] = ()
    endpoints: tuple[EndpointRecord, ...] = ()
    claims: tuple[ClaimRecord, ...] = ()
    issues: tuple[Issue, ...] = ()
    synthetic: bool = False

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def object_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise failure(Status.INVALID, "Expected a structured public metadata object")
    return value
