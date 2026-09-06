import itertools
import math
import random

import pytest
from buildbox_router.contracts import Assignment, Evidence, Fact, Node, Provenance
from buildbox_router.errors import DomainError
from buildbox_router.intelligence.selection import (
    DeterministicSelector,
    SafeDraftCompiler,
    projected_workflow_spend,
    token_component_cost,
)


def change_candidate(catalog, identifier, **changes):
    return catalog.model_copy(
        update={
            "configurations": tuple(
                c.model_copy(update=changes) if c.id == identifier else c
                for c in catalog.configurations
            )
        }
    )


def test_supported_contradicted_unknown_are_distinct(workflow, lane_catalog):
    selector = DeterministicSelector()
    assert selector.filter(workflow, lane_catalog).eligible == ("config-0", "config-1")
    assert selector.contradicted(workflow, lane_catalog) == ("config-2",)
    assert selector.needing_verification(workflow, lane_catalog) == ("config-3",)
    assert selector.rank_for_verification(workflow, lane_catalog) == ("config-3",)
    for decisions in selector.assess(workflow, lane_catalog).values():
        assert all(d.provenance.source.startswith("selection-1.0:") for d in decisions)
        assert all(d.provenance.evidence_ids == ("fixture-source",) for d in decisions)


@pytest.mark.parametrize("ceiling", [0, 0.1, 0.2, 0.9, 1])
def test_tightening_cost_never_adds_eligible_candidates(workflow, lane_catalog, ceiling):
    engine = DeterministicSelector()
    original = set(engine.filter(workflow, lane_catalog).eligible)
    tightened = workflow.model_copy(
        update={
            "constraints": workflow.constraints.model_copy(
                update={"max_cost_per_1k_tokens": ceiling}
            )
        }
    )
    assert set(engine.filter(tightened, lane_catalog).eligible) <= original


def test_missing_evidence_does_not_pass_mandatory_budget(workflow, lane_catalog):
    value = Fact[float](value=0.0, provenance=Provenance(kind="inference", source="Guessed cheap"))
    changed = change_candidate(lane_catalog, "config-0", cost_per_1k_tokens=value)
    assert "config-0" in DeterministicSelector().needing_verification(workflow, changed)


@pytest.mark.parametrize("price", [-1.0, math.inf, math.nan])
def test_invalid_prices_are_unavailable_not_cheap(workflow, lane_catalog, price):
    fact = lane_catalog.configurations[0].cost_per_1k_tokens.model_copy(update={"value": price})
    changed = change_candidate(lane_catalog, "config-0", cost_per_1k_tokens=fact)
    if math.isfinite(price):
        assert "config-0" not in DeterministicSelector().filter(workflow, changed).eligible
    else:
        with pytest.raises(ValueError):
            DeterministicSelector().filter(workflow, changed)


def test_listing_does_not_establish_download_or_legal_fit(workflow, lane_catalog):
    payload = lane_catalog.model_dump_json().replace('"kind":"synthetic"', '"kind":"documented"')
    catalog = (
        type(lane_catalog).model_validate_json(payload).model_copy(update={"synthetic": False})
    )
    engine = DeterministicSelector()
    assert not engine.filter(workflow, catalog).eligible
    assert "artifact_download_and_legal_scope" in " ".join(
        engine.filter(workflow, catalog).excluded["config-0"]
    )
    with pytest.raises(DomainError):
        engine.recommend(workflow, catalog, "rec")


@pytest.mark.parametrize(
    "requirement",
    [
        "context window",
        "output token",
        "commercial license",
        "zero retention",
        "on-prem",
        "hardware fit",
        "per workflow budget",
    ],
)
def test_unrepresentable_hard_requirements_block(workflow, lane_catalog, requirement):
    changed = workflow.model_copy(update={"title": "Must satisfy " + requirement})
    assert not DeterministicSelector().filter(changed, lane_catalog).eligible


def test_json_and_tool_support_not_inferred_from_model_listing(workflow, lane_catalog):
    changed = workflow.model_copy(
        update={
            "nodes": (
                workflow.nodes[0].model_copy(update={"purpose": "Return JSON with exact fields"}),
                workflow.nodes[1],
            )
        }
    )
    assert not DeterministicSelector().filter(changed, lane_catalog).eligible


def test_single_model_winner_and_no_model_steps(workflow, lane_catalog):
    engine = DeterministicSelector()
    rec = engine.recommend(workflow, lane_catalog, "rec")
    assert [(a.node_id, a.configuration_id) for a in rec.assignments] == [("classify", "config-0")]
    summary = engine.compare_stacks(workflow, lane_catalog)
    assert summary.configuration_ids == ("config-0",)
    assert "distinct models=1, configurations=1" in summary.rationale
    assert not summary.quality_verified and rec.confidence == "synthetic_only"
    assert rec.evidence_ids == ("fixture-source",) and rec.alternatives == ()


def test_deterministic_code_only_policy_needs_no_model(workflow, lane_catalog):
    pure = workflow.model_copy(
        update={"nodes": (Node(id="transform", kind="code", purpose="Lowercase text"),)}
    )
    engine = DeterministicSelector()
    rec = engine.recommend(pure, lane_catalog, "pure")
    assert not rec.assignments
    assert (
        "distinct models=0, configurations=0" in engine.compare_stacks(pure, lane_catalog).rationale
    )
    policy = SafeDraftCompiler(lane_catalog).compile(pure, rec)
    assert not policy.assignments and not policy.active


def exhaustive_reference(workflow, catalog):
    engine = DeterministicSelector()
    ranked = engine.rank(workflow, catalog, engine.filter(workflow, catalog))
    nodes = sorted(n.id for n in workflow.nodes if n.kind in ("llm", "bounded_agent"))
    scored = []
    # Independent full assignment product, unlike portfolio-first production search.
    for mapping in itertools.product(ranked, repeat=len(nodes)):
        count = len(set(mapping))
        if count <= 3:
            scored.append(
                ((sum(ranked.index(c) for c in mapping) + 2 * (count - 1), count, mapping), mapping)
            )
    return tuple(zip(nodes, min(scored)[1], strict=True))


@pytest.mark.parametrize("seed", range(16))
def test_optimizer_matches_exhaustive_reference_on_tiny_cases(workflow, lane_catalog, seed):
    rng = random.Random(seed)
    count = rng.randint(1, 4)
    configs = tuple(
        c.model_copy(
            update={
                "cost_per_1k_tokens": c.cost_per_1k_tokens.model_copy(
                    update={"value": rng.choice([0.0, 0.1, 0.2, 0.3]), "unknown_reason": None}
                )
            }
        )
        for c in lane_catalog.configurations[:count]
    )
    catalog = lane_catalog.model_copy(update={"configurations": tuple(reversed(configs))})
    nodes = tuple(
        Node(id=f"step-{i}", kind="llm", purpose="Classify text") for i in range(rng.randint(1, 3))
    )
    changed = workflow.model_copy(update={"nodes": nodes})
    rec = DeterministicSelector().recommend(changed, catalog, "rec")
    assert tuple((a.node_id, a.configuration_id) for a in rec.assignments) == exhaustive_reference(
        changed, catalog
    )
    assert "complete=yes" in DeterministicSelector().compare_stacks(changed, catalog).rationale


def test_search_truncation_is_disclosed(workflow, lane_catalog):
    comparison = DeterministicSelector(max_mappings=1).compare_stacks(workflow, lane_catalog)
    assert "complete=no" in comparison.rationale and "searched mappings=1" in comparison.rationale
    assert (
        "complete=no"
        in DeterministicSelector(max_candidates=1).compare_stacks(workflow, lane_catalog).rationale
    )


def test_stable_tie_break_and_catalog_permutation(workflow, lane_catalog):
    changed = change_candidate(
        lane_catalog,
        "config-1",
        cost_per_1k_tokens=lane_catalog.configurations[0].cost_per_1k_tokens,
    )
    engine = DeterministicSelector()
    one = engine.recommend(workflow, changed, "rec")
    two = engine.recommend(
        workflow,
        changed.model_copy(update={"configurations": tuple(reversed(changed.configurations))}),
        "rec",
    )
    assert one == two and one.assignments[0].configuration_id == "config-0"


def test_unknown_optional_price_is_not_zero(workflow, lane_catalog):
    relaxed = workflow.model_copy(
        update={
            "constraints": workflow.constraints.model_copy(update={"max_cost_per_1k_tokens": None})
        }
    )
    engine = DeterministicSelector()
    assert (
        engine.rank(relaxed, lane_catalog, engine.filter(relaxed, lane_catalog))[-1] == "config-3"
    )
    assert (
        engine.recommend(relaxed, lane_catalog, "rec").assignments[0].configuration_id == "config-0"
    )


def test_stale_filter_cannot_be_reused(workflow, lane_catalog):
    engine = DeterministicSelector()
    old = engine.filter(workflow, lane_catalog)
    tightened = workflow.model_copy(
        update={
            "constraints": workflow.constraints.model_copy(update={"max_cost_per_1k_tokens": 0})
        }
    )
    with pytest.raises(DomainError):
        engine.rank(tightened, lane_catalog, old)


def test_policy_refuses_incomplete_old_or_fallback_mappings(workflow, lane_catalog):
    rec = DeterministicSelector().recommend(workflow, lane_catalog, "rec")
    compiler = SafeDraftCompiler(lane_catalog)
    policy = compiler.compile(workflow, rec)
    assert policy.status == "draft" and policy.active is False and policy.production_write is False
    assert policy.requires_human_approval and not policy.execution_tools
    for bad in (
        rec.model_copy(update={"workflow_version": 2}),
        rec.model_copy(update={"assignments": ()}),
        rec.model_copy(update={"alternatives": ("config-3",)}),
        rec.model_copy(
            update={
                "assignments": (
                    Assignment(node_id="review", configuration_id="config-0", reason="wrong"),
                )
            }
        ),
    ):
        with pytest.raises(DomainError):
            compiler.compile(workflow, bad)


def test_edit_invalidates_old_recommendation_even_when_ranking_unchanged(workflow, lane_catalog):
    rec = DeterministicSelector().recommend(workflow, lane_catalog, "rec")
    revised = workflow.model_copy(
        update={"version": 2, "title": "New objective with unchanged constraints"}
    )
    with pytest.raises(DomainError):
        SafeDraftCompiler(lane_catalog).compile(revised, rec)


def test_policy_rechecks_tightened_requirements(workflow, lane_catalog):
    rec = DeterministicSelector().recommend(workflow, lane_catalog, "rec")
    tighter = workflow.model_copy(
        update={
            "constraints": workflow.constraints.model_copy(
                update={"required_region": "unavailable"}
            )
        }
    )
    with pytest.raises(DomainError):
        SafeDraftCompiler(lane_catalog).compile(tighter, rec)


def test_export_excludes_credential_bearing_free_text(workflow, lane_catalog):
    secret = "SYNTHETIC-SECRET-DO-NOT-EXPORT"
    rec = DeterministicSelector().recommend(workflow, lane_catalog, "rec")
    rec = rec.model_copy(
        update={
            "assignments": (rec.assignments[0].model_copy(update={"reason": secret}),),
            "limitations": (secret,),
        }
    )
    payload = SafeDraftCompiler(lane_catalog).compile(workflow, rec).model_dump_json()
    assert secret not in payload
    assert all(
        value not in payload.lower()
        for value in ("api_key", "password", "authorization", "endpoint")
    )


def test_cost_component_normalizes_units_and_missing_quantities(provenance, workflow):
    price = Fact[float](value=2.0, provenance=provenance)
    tokens = Fact[int](value=250, provenance=provenance)
    assert token_component_cost(price, tokens).value == 0.5
    assert (
        token_component_cost(
            price, Fact[int](provenance=provenance, unknown_reason="Missing tokens")
        ).value
        is None
    )
    assert (
        token_component_cost(
            Fact[float](provenance=provenance, unknown_reason="Missing price"), tokens
        ).value
        is None
    )
    assert projected_workflow_spend(workflow).value is None


def test_benchmarks_in_prose_are_not_averaged_or_parsed_as_capabilities(workflow, lane_catalog):
    prose = Evidence(
        id="unscoped-benchmark",
        title="No structured benchmark scope",
        claim="Model score 99 on benchmark A, 5 on unrelated B; tool support claimed",
        captured_at="2026-09-06",
        provenance=lane_catalog.evidence[0].provenance,
    )
    expanded = lane_catalog.model_copy(update={"evidence": (*lane_catalog.evidence, prose)})
    engine = DeterministicSelector()
    assert (
        engine.recommend(workflow, lane_catalog, "rec").assignments
        == engine.recommend(workflow, expanded, "rec").assignments
    )
    assert "unscoped-benchmark" not in engine.recommend(workflow, expanded, "rec").evidence_ids
