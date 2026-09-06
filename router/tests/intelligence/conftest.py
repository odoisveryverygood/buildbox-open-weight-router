"""Lane-owned synthetic inputs and catalog; no research-lane dependency."""

import pytest
from buildbox_router.contracts import (
    CandidateConfiguration,
    CatalogSnapshot,
    Evidence,
    Fact,
    ModelArtifact,
    Provenance,
)


@pytest.fixture
def lane_catalog():
    p = Provenance(
        kind="synthetic",
        source="Lane A synthetic recorded catalog",
        evidence_ids=("fixture-source",),
    )
    text = Fact[str](value="local", provenance=p)
    artifacts = tuple(
        ModelArtifact(
            id=f"artifact-{i}",
            name=f"Synthetic artifact {i}",
            revision="v1",
            open_weight=Fact[bool](value=True, provenance=p),
            license=Fact[str](provenance=p, unknown_reason="No real legal claim"),
            provenance=p,
        )
        for i in range(2)
    )
    configs = tuple(
        CandidateConfiguration(
            id=f"config-{i}",
            artifact_id=f"artifact-{i % 2}",
            provider=text,
            region=text,
            quantization=Fact[str](provenance=p, unknown_reason="Unmeasured"),
            hardware=Fact[str](provenance=p, unknown_reason="Unmeasured"),
            prompt_template_ref="prompt-v1",
            harness_ref="harness-v1",
            reasoning_budget=Fact[int](value=0, provenance=p),
            cost_per_1k_tokens=Fact[float](
                value=value, provenance=p, unknown_reason="Price missing" if value is None else None
            ),
            latency_ms=Fact[float](value=10.0, provenance=p),
            provenance=p,
        )
        for i, value in enumerate((0.0, 0.2, 2.0, None))
    )
    return CatalogSnapshot(
        id="lane-a-catalog",
        synthetic=True,
        artifacts=artifacts,
        configurations=configs,
        evidence=(
            Evidence(
                id="fixture-source",
                title="Synthetic evidence",
                claim="Invented facts for offline tests only",
                captured_at="2026-09-06",
                provenance=p,
            ),
        ),
    )
