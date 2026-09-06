from ..contracts import (
    CandidateConfiguration,
    CatalogSnapshot,
    Evidence,
    Fact,
    ModelArtifact,
    Provenance,
    Workflow,
)


class SyntheticCatalog:
    def snapshot(self) -> CatalogSnapshot:
        p = Provenance(
            kind="synthetic", source="Hand-authored test fixture", evidence_ids=("fixture-facts",)
        )
        unknown = Fact[str](provenance=p, unknown_reason="Not supplied by synthetic fixture")
        configurations = []
        for name, cost, region in (
            ("fixture-small-local", 0.0, "local"),
            ("fixture-medium-local", 0.4, "local"),
            ("fixture-over-budget", 4.0, "local"),
            ("fixture-other-region", 0.1, "remote"),
        ):
            configurations.append(
                CandidateConfiguration(
                    id=name,
                    artifact_id="synthetic-artifact",
                    provider=Fact[str](value="simulated", provenance=p),
                    region=Fact[str](value=region, provenance=p),
                    quantization=unknown,
                    hardware=unknown,
                    prompt_template_ref="fixture-classify-v1",
                    harness_ref="fixture-harness-v1",
                    reasoning_budget=Fact[int](value=0, provenance=p),
                    cost_per_1k_tokens=Fact[float](value=cost, provenance=p),
                    latency_ms=Fact[float](provenance=p, unknown_reason="Never benchmarked"),
                    provenance=p,
                )
            )
        return CatalogSnapshot(
            id="synthetic-catalog-v1",
            synthetic=True,
            artifacts=(
                ModelArtifact(
                    id="synthetic-artifact",
                    name="SYNTHETIC artifact — not a released model",
                    revision="fixture-v1",
                    open_weight=Fact[bool](value=True, provenance=p),
                    license=unknown,
                    provenance=p,
                ),
            ),
            configurations=tuple(configurations),
            evidence=(
                Evidence(
                    id="fixture-facts",
                    title="Synthetic configuration evidence",
                    claim="All prices, regions and artifact facts are invented solely for software tests. No real model performance is asserted.",
                    captured_at="2026-09-06",
                    provenance=p,
                ),
            ),
        )

    def research(self, workflow: Workflow) -> CatalogSnapshot:
        return self.snapshot()
