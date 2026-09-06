"""Three finite public research roles; deterministic parsing needs no LLM prompts.

Role/parser versions are recorded. Inputs contain approved public identities and
source locators only. Workflows/private examples cannot be job inputs.
"""

import json
import re
from typing import Literal

from pydantic import Field, model_validator

from .bounds import BoundedReader
from .evidence import claim
from .normalizers import artifact_from_hub, endpoints_from_openrouter
from .records import (
    ArtifactRecord,
    ClaimRecord,
    EndpointRecord,
    FreshnessPolicy,
    Issue,
    Record,
    ResearchFailure,
    SourceCapture,
    Status,
    failure,
)
from .sources import discovery_query


class ArtifactInput(Record):
    repositories: tuple[str, ...] = Field(min_length=1, max_length=12)


class ArtifactOutput(Record):
    role: Literal["artifact-discovery-1"] = "artifact-discovery-1"
    artifacts: tuple[ArtifactRecord, ...]
    claims: tuple[ClaimRecord, ...]
    issues: tuple[Issue, ...]


class CapabilitySpec(Record):
    """Reviewed locator for one exact row/column; no fuzzy matching across models."""

    repository: str
    source_url: str
    source_locator: str
    header: str
    row: str
    column: int = Field(ge=1, le=30)
    column_label: str
    benchmark: str
    version: str | None = None
    split: str | None = None
    unit: str | None = None
    settings: str | None = None
    methodology_quote: str | None = None
    harness: str | None = None
    harness_quote: str | None = None
    sample_size: int | None = Field(default=None, ge=1)


class CapabilityInput(Record):
    artifacts: tuple[ArtifactRecord, ...]
    specifications: tuple[CapabilitySpec, ...] = Field(default=(), max_length=24)


class CapabilityOutput(Record):
    role: Literal["capability-evidence-1"] = "capability-evidence-1"
    claims: tuple[ClaimRecord, ...]
    issues: tuple[Issue, ...]


class DeploymentSpec(Record):
    repository: str
    model_url: str
    endpoint_url: str


class DeploymentInput(Record):
    artifacts: tuple[ArtifactRecord, ...]
    specifications: tuple[DeploymentSpec, ...] = Field(default=(), max_length=12)


class DeploymentOutput(Record):
    role: Literal["deployment-evidence-1"] = "deployment-evidence-1"
    endpoints: tuple[EndpointRecord, ...]
    claims: tuple[ClaimRecord, ...]
    issues: tuple[Issue, ...]


def stop_issue(exc: ResearchFailure) -> bool:
    return exc.issue.status in (Status.CANCELLED, Status.TIMEOUT, Status.BUDGET)


class ArtifactDiscovery:
    def run(
        self, inputs: ArtifactInput, reader: BoundedReader, policy: FreshnessPolicy
    ) -> ArtifactOutput:
        artifacts: list[ArtifactRecord] = []
        claims: list[ClaimRecord] = []
        issues: list[Issue] = []
        for repository in inputs.repositories:
            try:
                reader.check()
                # Exact identities exist before independent downstream jobs begin.
                url = f"https://huggingface.co/api/models/{repository}"
                discovery_query(repository)  # validates public-only identity syntax
                source = reader.read(url)
                artifact, rows = artifact_from_hub(repository, source, policy)
                artifacts.append(artifact)
                claims.extend(rows)
            except ResearchFailure as exc:
                issues.append(exc.issue)
                if stop_issue(exc):
                    break
        return ArtifactOutput(
            artifacts=tuple(artifacts), claims=tuple(claims), issues=tuple(issues)
        )


def clean_cell(text: str) -> str:
    return re.sub(r"[*`]", "", text).strip()


def table_metric(source: SourceCapture, spec: CapabilitySpec) -> str:
    """Extract only the reviewed table cells; surrounding instructions are inert."""
    lines = source.body.splitlines()
    if lines.count(spec.header) != 1 or lines.count(spec.row) != 1:
        raise failure(Status.CONFLICT, "Exact benchmark table locator missing or ambiguous")
    header = [clean_cell(x) for x in spec.header.strip().strip("|").split("|")]
    row = [clean_cell(x) for x in spec.row.strip().strip("|").split("|")]
    if (
        len(row) != len(header)
        or spec.column >= len(row)
        or header[spec.column] != spec.column_label
    ):
        raise failure(Status.CONFLICT, "Benchmark header/column mismatch")
    if spec.methodology_quote and spec.methodology_quote not in source.body:
        raise failure(Status.CONFLICT, "Benchmark settings lack the cited methodology excerpt")
    if spec.harness_quote and spec.harness_quote not in source.body:
        raise failure(Status.CONFLICT, "Benchmark harness lacks the cited source excerpt")
    value = row[spec.column]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?%?", value):
        raise failure(Status.PARTIAL, "Benchmark cell is not a scalar metric")
    return value


class CapabilityEvidence:
    def run(
        self, inputs: CapabilityInput, reader: BoundedReader, policy: FreshnessPolicy
    ) -> CapabilityOutput:
        by_repo = {a.repository_id: a for a in inputs.artifacts}
        claims: list[ClaimRecord] = []
        issues: list[Issue] = []
        covered: set[str] = set()
        for spec in inputs.specifications:
            artifact = by_repo.get(spec.repository)
            if artifact is None:
                continue
            try:
                source = reader.read(spec.source_url)
                claims.append(capability_claim(source, spec, artifact, policy))
                covered.add(spec.repository)
            except ResearchFailure as exc:
                issues.append(exc.issue)
                if stop_issue(exc):
                    break
        for repository in sorted(set(by_repo) - covered):
            issues.append(
                Issue(
                    status=Status.PARTIAL,
                    subject=by_repo[repository].artifact.id,
                    message="No validated benchmark cell in this bounded snapshot; capability remains unknown",
                )
            )
        return CapabilityOutput(claims=tuple(claims), issues=tuple(issues))


def capability_claim(
    source: SourceCapture, spec: CapabilitySpec, artifact: ArtifactRecord, policy: FreshnessPolicy
) -> ClaimRecord:
    expected_url = (
        f"https://huggingface.co/{spec.repository}/raw/{artifact.artifact.revision}/README.md"
    )
    if source.source_type != "publisher_card" or source.url != expected_url:
        raise failure(Status.CONFLICT, "Capability source is not the pinned publisher card")
    metric = table_metric(source, spec)
    return claim(
        source,
        subject=artifact.artifact.id,
        kind="artifact",
        field="capability",
        locator=spec.source_locator,
        text=f"Publisher table for {spec.repository}: {spec.benchmark} reports {metric}. Not a Buildbox workload test.",
        policy=policy,
        metric=metric,
        unit=spec.unit,
        benchmark=spec.benchmark,
        benchmark_version=spec.version,
        split=spec.split,
        settings=spec.settings if spec.methodology_quote else None,
        harness=spec.harness if spec.harness_quote else None,
        sample_size=spec.sample_size if spec.methodology_quote else None,
        limitations=(
            "Publisher-reported metric, not independently reproduced.",
            "Incomplete version/split/harness/sample size remain Unknown; cannot rank across unlike setups.",
            "Retrieval date is not the benchmark measurement date.",
        ),
    )


class DeploymentEvidence:
    def run(
        self, inputs: DeploymentInput, reader: BoundedReader, policy: FreshnessPolicy
    ) -> DeploymentOutput:
        by_repo = {a.repository_id: a for a in inputs.artifacts}
        endpoints: list[EndpointRecord] = []
        claims: list[ClaimRecord] = []
        issues: list[Issue] = []
        covered: set[str] = set()
        for spec in inputs.specifications:
            artifact = by_repo.get(spec.repository)
            if artifact is None:
                continue
            try:
                model_source = reader.read(spec.model_url)
                endpoint_source = reader.read(spec.endpoint_url)
                records, rows = endpoints_from_openrouter(
                    artifact, model_source, endpoint_source, policy
                )
                endpoints.extend(records)
                claims.extend(rows)
                if records:
                    covered.add(spec.repository)
            except ResearchFailure as exc:
                issues.append(exc.issue)
                if stop_issue(exc):
                    break
        for repository in sorted(set(by_repo) - covered):
            issues.append(
                Issue(
                    status=Status.PARTIAL,
                    subject=by_repo[repository].artifact.id,
                    message="No identity-matched endpoint captured; this is not proof that no endpoint exists",
                )
            )
        return DeploymentOutput(
            endpoints=tuple(endpoints), claims=tuple(claims), issues=tuple(issues)
        )


class ResearchPlan(Record):
    artifacts: ArtifactInput
    capabilities: tuple[CapabilitySpec, ...] = Field(default=(), max_length=24)
    deployments: tuple[DeploymentSpec, ...] = Field(default=(), max_length=12)

    @model_validator(mode="after")
    def bounded_public_plan(self) -> "ResearchPlan":
        repositories = self.artifacts.repositories
        if len(set(repositories)) != len(repositories):
            raise ValueError("Duplicate artifact discovery identity")
        for repository in repositories:
            discovery_query(repository)
        if any(s.repository not in repositories for s in self.capabilities) or any(
            s.repository not in repositories for s in self.deployments
        ):
            raise ValueError("Research evidence must refer to a planned public identity")
        if len({(s.source_url, s.source_locator) for s in self.capabilities}) != len(
            self.capabilities
        ):
            raise ValueError("Duplicate capability source locator")
        return self

    def cache_key(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True)
