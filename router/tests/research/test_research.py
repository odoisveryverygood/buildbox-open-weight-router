from buildbox_router.research.fixture import SyntheticCatalog


def test_catalog_is_explicitly_synthetic_and_repeatable():
    first = SyntheticCatalog().snapshot()
    assert first == SyntheticCatalog().snapshot()
    assert first.synthetic
    assert all(x.provenance.kind == "synthetic" for x in first.configurations)
    assert len(first.artifacts) == 1 and len(first.configurations) == 4


def test_artifact_and_endpoint_facts_are_separate():
    snapshot = SyntheticCatalog().snapshot()
    assert not hasattr(snapshot.artifacts[0], "provider")
    assert all(c.artifact_id == snapshot.artifacts[0].id for c in snapshot.configurations)
    assert snapshot.configurations[0].cost_per_1k_tokens.value == 0
    assert snapshot.configurations[0].latency_ms.value is None
    assert snapshot.configurations[0].latency_ms.unknown_reason


def test_research_snapshot_never_executes_workflow(workflow):
    assert SyntheticCatalog().research(workflow) == SyntheticCatalog().snapshot()
