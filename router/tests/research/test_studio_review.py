from datetime import timedelta

import pytest
from buildbox_router.research.review import refresh_issues, snapshot_changes
from buildbox_router.research.service import PublicResearch


@pytest.fixture
def ledger(sources, plan, storage, now):
    return PublicResearch(sources=sources, plan=plan, storage=storage).run(now=now).ledger()


def test_review_is_bounded_and_read_only(ledger, now):
    before = ledger.model_dump_json()
    endpoint = ledger.endpoints[0]
    issues = refresh_issues(ledger, frozenset([endpoint.id]), now + timedelta(hours=7))
    assert len(issues) == 1
    assert issues[0].subject == endpoint.id and issues[0].status == "stale_data"
    assert "pricing" in issues[0].message
    assert ledger.model_dump_json() == before
    assert not refresh_issues(ledger, frozenset(), now)


def test_missing_subject_not_ineligible(ledger, now):
    issue = refresh_issues(ledger, frozenset(["missing-public-id"]), now)[0]
    assert issue.status == "partial_coverage" and "unknown" in issue.message
    with pytest.raises(ValueError):
        refresh_issues(ledger, frozenset(), now.replace(tzinfo=None))


def test_same_snapshot_no_changes(ledger):
    assert snapshot_changes(ledger, ledger) == ()


def test_removed_claim_not_absence_of_capability(ledger):
    after = ledger.model_copy(update={"claims": ledger.claims[1:]})
    assert "not proof" in snapshot_changes(ledger, after)[0].message


def test_recapture_not_new_measurement(ledger):
    row = ledger.claims[0]
    newer = row.model_copy(
        update={
            "observed_at": row.observed_at + timedelta(seconds=1),
            "expires_at": row.expires_at + timedelta(seconds=1),
        }
    )
    after = ledger.model_copy(update={"claims": (newer, *ledger.claims[1:])})
    assert "not a new benchmark" in snapshot_changes(ledger, after)[0].message


def test_changed_content_and_duplicate_locator_retained(ledger):
    row = ledger.claims[0]
    newer = row.model_copy(update={"source_digest": "changed"})
    after = ledger.model_copy(update={"claims": (newer, *ledger.claims[1:])})
    assert "content changed" in snapshot_changes(ledger, after)[0].message
    duplicate = ledger.model_copy(update={"claims": (*ledger.claims, newer)})
    assert snapshot_changes(ledger, duplicate)[0].status == "source_conflict"


def test_public_synthetic_populations_do_not_mix(ledger):
    assert (
        snapshot_changes(ledger, ledger.model_copy(update={"synthetic": True}))[0].status
        == "invalid_evidence"
    )
