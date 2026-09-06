import json
import threading
from datetime import timedelta

import pytest
from buildbox_router.contracts import Fact
from buildbox_router.errors import DomainError
from buildbox_router.research.bounds import BoundedReader, BudgetLedger, Limits
from buildbox_router.research.catalog import (
    ConfigurationBinding,
    SnapshotCatalog,
    publish,
    validate_ledger,
)
from buildbox_router.research.evidence import conflicts
from buildbox_router.research.jobs import CapabilityEvidence, CapabilityInput, table_metric
from buildbox_router.research.records import ResearchFailure, Status
from buildbox_router.research.service import PublicResearch
from buildbox_router.research.sources import RecordedSources


def run(sources, plan, storage, now, **kwargs):
    service = PublicResearch(sources=sources, plan=plan, storage=storage, **kwargs)
    return service, service.run(now=now)


def test_complete_public_snapshot_is_immutable_and_not_quality_validation(
    sources, plan, storage, now
):
    service, catalog = run(sources, plan, storage, now)
    snapshot, ledger = catalog.snapshot(), catalog.ledger()
    assert len(snapshot.artifacts) == 8 and len(ledger.endpoints) == 1
    assert len(ledger.claims) == 32
    assert len([c for c in ledger.claims if c.field == "capability"]) == 5
    assert not snapshot.synthetic
    assert snapshot.configurations == ()
    assert all(not c.measured_by_us for c in ledger.claims)
    assert all(c.tested_at.value is None for c in ledger.claims)
    assert all(c.sample_size.value is None for c in ledger.claims)
    assert service.last_budget.usage[0] == 15
    restored = SnapshotCatalog(storage, snapshot.id)
    assert restored.snapshot() == snapshot and restored.ledger() == ledger
    with pytest.raises(DomainError):
        storage.put("another-owner", "public_catalog", snapshot.id, "{}")


def test_fresh_cache_makes_no_source_calls(sources, plan, storage, now, monkeypatch):
    service, first = run(sources, plan, storage, now)

    def forbidden(**kwargs):
        raise AssertionError("Fresh cache must avoid source adapter calls")

    monkeypatch.setattr(sources, "extract", forbidden)
    second = service.run(now=now + timedelta(minutes=1))
    assert second.snapshot() == first.snapshot()
    assert service.last_budget.usage[0] == 0


def test_price_refresh_only_fetches_deployment_sources(sources, captures, plan, storage, now):
    _, frozen = run(sources, plan, storage, now)
    original_bytes = frozen.snapshot().model_dump_json()
    refreshed_at = now + timedelta(hours=7)
    newer = []
    for source in captures:
        if source.source_type == "official_endpoint":
            source = source.model_copy(update={"observed_at": refreshed_at})
        newer.append(source)
    service, refreshed = run(RecordedSources(newer), plan, storage, refreshed_at, cached=frozen)
    assert service.last_budget.usage[0] == 2
    assert refreshed.snapshot_id != frozen.snapshot_id
    assert frozen.snapshot().model_dump_json() == original_bytes
    assert refreshed.ledger().artifacts == frozen.ledger().artifacts


def test_stale_replay_does_not_fabricate_refresh_dates(sources, plan, storage, now):
    _, first = run(sources, plan, storage, now)
    later = now + timedelta(days=40)
    _, stale = run(sources, plan, storage, later, cached=first)
    assert any(i.status == Status.STALE for i in stale.ledger().issues)
    assert [c.observed_at for c in first.ledger().claims] == [
        c.observed_at for c in stale.ledger().claims
    ]


def test_future_observations_are_rejected(sources, plan, storage, now):
    with pytest.raises(ResearchFailure) as exc:
        run(sources, plan, storage, now - timedelta(days=1))
    assert exc.value.issue.status == Status.INVALID


def test_field_freshness_is_configurable(sources, plan, storage, now, freshness):
    _, catalog = run(
        sources,
        plan,
        storage,
        now,
        policy=freshness.model_copy(update={"pricing_seconds": 100, "license_seconds": 500}),
    )
    ledger = catalog.ledger()
    assert all(
        (c.expires_at - c.observed_at).total_seconds() == 100
        for c in ledger.claims
        if c.field == "pricing"
    )
    assert all(
        (c.expires_at - c.observed_at).total_seconds() == 500
        for c in ledger.claims
        if c.field == "license"
    )


def test_cancelled_research_never_publishes(sources, plan, storage, now):
    event = threading.Event()
    event.set()
    service = PublicResearch(sources=sources, plan=plan, storage=storage, cancelled=event)
    with pytest.raises(ResearchFailure) as exc:
        service.run(now=now)
    assert exc.value.issue.status == Status.CANCELLED and service.cached is None


def test_budget_exhaustion_no_partial_publication(sources, plan, storage, now):
    service = PublicResearch(
        sources=sources, plan=plan, storage=storage, limits=Limits(max_calls=3)
    )
    with pytest.raises(ResearchFailure) as exc:
        service.run(now=now)
    assert exc.value.issue.status == Status.BUDGET
    assert service.cached is None and service.last_budget.usage[0] == 3


def test_no_private_workflow_text_enters_sources_or_public_ledger(
    sources, plan, storage, now, workflow, monkeypatch
):
    secret = "PRIVATE_CUSTOMER_DOCUMENT_DO_NOT_TRANSMIT_7193"
    workflow = workflow.model_copy(update={"title": secret})
    captured = []
    original = sources.extract

    def trace(*, url):
        captured.append(url)
        return original(url=url)

    monkeypatch.setattr(sources, "extract", trace)
    service = PublicResearch(sources=sources, plan=plan, storage=storage)
    snapshot = service.research(workflow)
    assert secret not in snapshot.model_dump_json()
    assert secret not in service.cached.ledger().model_dump_json()
    assert secret not in json.dumps(captured)
    assert all(
        url.startswith(("https://huggingface.co/", "https://openrouter.ai/")) for url in captured
    )


def test_exact_benchmark_subject_no_series_score_copy(sources, plan, storage, now):
    _, catalog = run(sources, plan, storage, now)
    artifact = next(
        a for a in catalog.ledger().artifacts if a.repository_id == "Qwen/Qwen3-Embedding-0.6B"
    )
    metric = next(
        c
        for c in catalog.ledger().claims
        if c.subject_id == artifact.artifact.id and c.field == "capability"
    )
    assert metric.raw_metric.value == "64.33"
    assert metric.raw_metric.value != "70.58"  # score from the different 8B model
    assert metric.benchmark_version.value is None
    assert metric.tested_at.value is None  # competitors' retrieval date is not this test's date


def test_mismatched_benchmark_header_is_rejected(sources, plan):
    spec = plan.capabilities[0]
    bad = spec.model_copy(update={"column_label": "Some other model score"})
    with pytest.raises(ResearchFailure):
        table_metric(sources.capture(spec.source_url), bad)


def test_unsupported_capability_source_remains_partial(sources, plan, storage, now, freshness):
    _, catalog = run(sources, plan, storage, now)
    reader = BoundedReader(sources, BudgetLedger(Limits()), threading.Event())
    try:
        result = CapabilityEvidence().run(
            CapabilityInput(artifacts=catalog.ledger().artifacts), reader, freshness
        )
    finally:
        reader.close()
    assert not result.claims and len(result.issues) == 8
    assert all(i.status == Status.PARTIAL for i in result.issues)


def test_conflicting_metrics_retained_without_averaging(sources, plan, storage, now):
    _, catalog = run(sources, plan, storage, now)
    first = next(c for c in catalog.ledger().claims if c.raw_metric.value is not None)
    other = first.model_copy(
        update={"raw_metric": Fact[str](value="0.01", provenance=first.raw_metric.provenance)}
    )
    assert conflicts((first, other))[0].status == Status.CONFLICT
    assert first.raw_metric.value != other.raw_metric.value


def test_different_benchmark_settings_not_averaged_or_conflated(sources, plan, storage, now):
    _, catalog = run(sources, plan, storage, now)
    first = next(c for c in catalog.ledger().claims if c.raw_metric.value is not None)
    other = first.model_copy(
        update={
            "raw_metric": Fact[str](value="0.01", provenance=first.raw_metric.provenance),
            "settings": Fact[str](
                value="different harness settings", provenance=first.settings.provenance
            ),
        }
    )
    assert conflicts((first, other)) == ()


@pytest.mark.parametrize("field", ["license", "metric", "expiry", "digest"])
def test_forged_job_proposals_cannot_publish(sources, plan, storage, now, field):
    _, catalog = run(sources, plan, storage, now)
    ledger = catalog.ledger()
    if field == "license":
        artifact = ledger.artifacts[0]
        fake = artifact.model_copy(
            update={
                "artifact": artifact.artifact.model_copy(
                    update={
                        "license": Fact[str](
                            value="fabricated", provenance=artifact.artifact.license.provenance
                        )
                    }
                )
            }
        )
        ledger = ledger.model_copy(update={"artifacts": (fake,) + ledger.artifacts[1:]})
    else:
        index = next(i for i, c in enumerate(ledger.claims) if c.field == "capability")
        row = ledger.claims[index]
        changes = {
            "metric": {"raw_metric": Fact[str](value="100", provenance=row.raw_metric.provenance)},
            "expiry": {"expires_at": now + timedelta(days=900)},
            "digest": {"source_digest": "fake"},
        }[field]
        rows = list(ledger.claims)
        rows[index] = row.model_copy(update=changes)
        ledger = ledger.model_copy(update={"claims": tuple(rows)})
    with pytest.raises(ResearchFailure):
        validate_ledger(ledger, sources, plan)


def test_explicit_binding_keeps_unknown_cost_and_latency(sources, plan, storage, now):
    _, catalog = run(sources, plan, storage, now)
    endpoint = catalog.ledger().endpoints[0]
    bound = publish(
        catalog.ledger(),
        sources,
        plan,
        storage,
        (
            ConfigurationBinding(
                endpoint_id=endpoint.id,
                prompt_template_ref="reviewed-prompt-v1",
                harness_ref="reviewed-harness-v1",
            ),
        ),
    )
    config = bound.snapshot().configurations[0]
    assert config.cost_per_1k_tokens.value is None and config.latency_ms.value is None
    assert config.prompt_template_ref == "reviewed-prompt-v1"


def test_mutating_returned_nested_objects_cannot_change_persisted_snapshot(
    sources, plan, storage, now
):
    _, catalog = run(sources, plan, storage, now)
    original = catalog.ledger().canonical_json()
    loaded = catalog.ledger()
    changed = loaded.model_copy(update={"issues": ()})
    assert changed.issues == ()
    assert catalog.ledger().canonical_json() == original


def test_forged_measured_flag_rejected_by_publication(sources, plan, storage, now):
    _, catalog = run(sources, plan, storage, now)
    ledger = catalog.ledger()
    rows = list(ledger.claims)
    rows[0] = rows[0].model_copy(update={"measured_by_us": True})
    with pytest.raises(ResearchFailure):
        validate_ledger(ledger.model_copy(update={"claims": tuple(rows)}), sources, plan)
