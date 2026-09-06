"""Executable reproductions of frozen-contract blockers, not patched contracts."""

import inspect

import pytest
from buildbox_router.contracts import Evidence, Provenance
from buildbox_router.ports import SearchPort
from pydantic import ValidationError


def test_v1_evidence_rejects_required_rich_provenance_fields():
    data = Evidence(
        id="source-1",
        title="Public benchmark",
        claim="Publisher claim",
        captured_at="2026-09-06",
        provenance=Provenance(kind="documented", source="Publisher metadata"),
    ).model_dump()
    data.update(
        subject_id="artifact-1", source_locator="README.md:L10", expires_at="2026-09-07T00:00:00Z"
    )
    with pytest.raises(ValidationError) as exc:
        Evidence.model_validate(data)
    assert {error["type"] for error in exc.value.errors()} == {"extra_forbidden"}


def test_frozen_search_port_cannot_express_required_transport_controls():
    parameters = inspect.signature(SearchPort.extract).parameters
    assert set(parameters) == {"self", "url"}
    assert "deadline" not in parameters
    assert "cancelled" not in parameters
    assert "reservation" not in parameters
    # A bare str cannot carry final URL, redirect chain, byte accounting or HTTP status.
    assert inspect.signature(SearchPort.extract).return_annotation is str
