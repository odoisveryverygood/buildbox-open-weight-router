"""Read-only snapshot review, using canonical evidence/issues; never routing authority.

The studio receives the same ledger through PlanningResult. These helpers prepare
bounded refresh/change diagnostics for a future shared list/refresh endpoint, not
a second catalog wire contract or scheduler. No private workflow is accepted.
"""

from datetime import datetime

from .records import ClaimRecord, Issue, ResearchLedger, Status


def claim_key(row: ClaimRecord) -> tuple[str, str, str, str, str]:
    return (
        row.subject_kind,
        row.subject_id,
        row.field,
        row.evidence.source_url or "",
        row.source_locator,
    )


def refresh_issues(
    ledger: ResearchLedger, subjects: frozenset[str], now: datetime
) -> tuple[Issue, ...]:
    """Only relevant expired/missing fields; cached observations are never restamped."""
    if now.tzinfo is None:
        raise ValueError("Review time must have a timezone")
    issues = []
    for subject in sorted(subjects):
        artifact = next((a for a in ledger.artifacts if a.artifact.id == subject), None)
        endpoint = next((e for e in ledger.endpoints if e.id == subject), None)
        fields = (
            ("identity", "license", "access", "capability")
            if artifact
            else ("deployment", "pricing")
            if endpoint
            else ()
        )
        if not fields:
            issues.append(
                Issue(
                    status=Status.PARTIAL,
                    subject=subject,
                    message="Subject not in this bounded snapshot; eligibility remains unknown",
                )
            )
        for field in fields:
            rows = [r for r in ledger.claims if r.subject_id == subject and r.field == field]
            if not rows:
                issues.append(
                    Issue(
                        status=Status.PARTIAL,
                        subject=subject,
                        message=f"Missing {field} evidence; no negative eligibility inference",
                    )
                )
            for row in rows:
                if row.observed_at > now or row.expires_at <= now:
                    issues.append(
                        Issue(
                            status=Status.INVALID if row.observed_at > now else Status.STALE,
                            subject=subject,
                            message=f"Review {field} claim {row.evidence.id}; original observation/expiry retained",
                        )
                    )
    return tuple(issues)


def snapshot_changes(before: ResearchLedger, after: ResearchLedger) -> tuple[Issue, ...]:
    """Distinguish claim content from recapture dates; preserve conflicts, never average."""
    if before.synthetic != after.synthetic:
        return (
            Issue(
                status=Status.INVALID,
                subject="snapshot",
                message="Synthetic/public snapshots are not comparable evidence populations",
            ),
        )
    old = {claim_key(row): row for row in before.claims}
    new = {claim_key(row): row for row in after.claims}
    # A dict must never hide multiple claims at the same locator.
    if len(old) != len(before.claims) or len(new) != len(after.claims):
        return (
            Issue(
                status=Status.CONFLICT,
                subject="snapshot",
                message="Multiple claims share a subject/field/source/locator; inspect separately",
            ),
        )
    issues = []
    for key in sorted(old.keys() | new.keys()):
        previous, current = old.get(key), new.get(key)
        if previous == current:
            continue
        if not previous or not current:
            message = (
                "New source-backed claim proposed, not a newly eligible configuration"
                if current
                else "Claim absent from new bounded snapshot; not proof of capability removal"
            )
        elif (
            previous.evidence.claim != current.evidence.claim
            or previous.raw_metric.value != current.raw_metric.value
            or previous.metric_unit.value != current.metric_unit.value
            or previous.source_digest != current.source_digest
        ):
            message = "Claim/source content changed; inspect both observations before using it"
        else:
            message = (
                "Provenance/freshness changed without a claim change; not a new benchmark test"
            )
        issues.append(Issue(status=Status.PARTIAL, subject=key[1], message=f"{key[2]}: {message}"))
    return tuple(issues)
