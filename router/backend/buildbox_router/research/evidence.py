"""Evidence annotation and conflict detection. No averaging or quality ranking."""

import json

from ..contracts import Evidence, Fact, Provenance
from .records import ClaimRecord, FreshnessPolicy, Issue, SourceCapture, Status, stable_id


def claim(
    source: SourceCapture,
    *,
    subject: str,
    kind: str,
    field: str,
    locator: str,
    text: str,
    policy: FreshnessPolicy,
    limitations: tuple[str, ...] = ("Publisher declaration; no workload test was run.",),
    metric: str | None = None,
    unit: str | None = None,
    split: str | None = None,
    benchmark: str | None = None,
    benchmark_version: str | None = None,
    harness: str | None = None,
    settings: str | None = None,
    sample_size: int | None = None,
    publication_date: str | None = None,
    tested_at: str | None = None,
) -> ClaimRecord:
    evidence_id = stable_id("evidence", subject, field, source.url, source.digest, locator, text)
    p = Provenance(
        kind="synthetic" if source.synthetic else "documented",
        source=source.url,
        evidence_ids=(evidence_id,),
    )

    def fact(value: str | None, name: str) -> Fact[str]:
        return Fact[str](
            value=value,
            provenance=p,
            unknown_reason=f"{name} not supplied by this source" if value is None else None,
        )

    # Pydantic validates the finite lane vocabulary, including source and subject types.
    return ClaimRecord.model_validate(
        {
            "evidence": Evidence(
                id=evidence_id,
                title=f"{field.title()} declaration",
                claim=text,
                source_url=source.url,
                captured_at=source.observed_at.isoformat(),
                provenance=p,
            ),
            "subject_id": subject,
            "subject_kind": kind,
            "field": field,
            "source_id": source.id,
            "source_type": source.source_type,
            "source_locator": locator,
            "source_digest": source.digest,
            "observed_at": source.observed_at,
            "expires_at": policy.expiry(field, source.observed_at),
            "publication_date": fact(publication_date, "Publication date"),
            "tested_at": fact(tested_at, "Benchmark test date (retrieval is not measurement)"),
            "raw_metric": fact(metric, "Metric"),
            "metric_unit": fact(unit, "Metric unit"),
            "benchmark_name": fact(benchmark, "Benchmark name"),
            "benchmark_version": fact(benchmark_version, "Benchmark version"),
            "benchmark_split": fact(split, "Benchmark split"),
            "harness": fact(harness, "Harness/version"),
            "settings": fact(settings, "Evaluation settings"),
            "sample_size": Fact[int](
                value=sample_size,
                provenance=p,
                unknown_reason="Sample size not supplied" if sample_size is None else None,
            ),
            "limitations": limitations,
        }
    )


def conflicts(claims: tuple[ClaimRecord, ...]) -> tuple[Issue, ...]:
    """Flag disagreeing directly comparable metrics; keep every source untouched."""
    groups: dict[tuple[str, ...], set[str]] = {}
    for row in claims:
        if row.raw_metric.value is None:
            continue
        key = (
            row.subject_id,
            row.field,
            json.dumps(
                [
                    row.metric_unit.value,
                    row.benchmark_name.value,
                    row.benchmark_version.value,
                    row.benchmark_split.value,
                    row.harness.value,
                    row.settings.value,
                ]
            ),
        )
        groups.setdefault(key, set()).add(row.raw_metric.value)
    return tuple(
        Issue(
            status=Status.CONFLICT,
            subject=key[0],
            message="Sources disagree on comparable evidence; values retained separately",
        )
        for key, values in sorted(groups.items())
        if len(values) > 1
    )
