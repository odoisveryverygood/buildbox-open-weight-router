# Lane B request: shared protected research transport and budgets

Base: `b36437fc91b717b3978f977ec3cdf084c8206a5b`.
Status: blocked for live networking; deterministic normalization/replay is complete.

## Missing shared capability

The frozen `SearchPort` offers only `search(query, limit) -> tuple[str, ...]` and
`extract(url) -> str`. Foundation `OfflineSearch` rejects calls. There is no shared
fetch protection implementation, timeout/cancellation contract, redirect/connection
receipt, or authoritative durable spending reservation. Lane B must not create a
competing shared transport or copy session credentials to bridge this gap.

The integration owner should supply a tested read-only public transport with:

- Approved schemes/domains and bounded URLs, query/result counts and response sizes.
- DNS/IP checks at the actual connection boundary (including IPv4/IPv6/private,
  link-local, loopback, mapped-address and rebinding cases), TLS hostname validation,
  approved ports, and destination validation before every redirect/connection.
- Deadlines, cancellation, bounded retries/backoff, HTTP status/429 reporting,
  final URL and redirect receipts, source retrieval times and byte accounting.
- Independent runtime authentication/configuration injection; no account creation,
  session-token reuse or import-time credential clients.
- An approval reference, per-call ceilings and durable cross-process reservations
  before dispatch. Unknown/time-out charges must remain reserved conservatively.
  One role must not change global budget or tools. Model assistance, if introduced,
  needs token/request bounds through the integration-owned inference adapter.

The owner can choose Bright Data for authorized public search/extraction or direct
official metadata endpoints for this narrow path; Exa is optional. No paid search
cap or runtime key/zone was approved in this lane, so no paid call was attempted.
Unauthenticated development metadata reads do not authorize a deployed adapter.

## Executable examples and honest test boundary

`test_shared_contract_requests.py` shows the frozen extraction signature cannot
carry a deadline, cancellation signal or reservation. `test_security_and_bounds.py`
checks `RuntimePublicSearch` refuses even a seemingly safe URL and any redirect
scenario; it never opens a socket. This is fail-closed behavior, not a passed test
of a live DNS/redirect implementation. The reference checks in `RecordedSources`
only protect exact offline lookup and are explicitly not a duplicate fetch guard.

The lane implements thread-safe reservations across the three jobs in one run,
bounded source replay, rate-limit retry caps, deadlines and cancellation before
publication. Its worker threads only read immutable captured bytes. A timed-out
Python call may finish later, but cannot publish, retry or refund its reservation.
Hard runtime cancellation and global accounting across processes need the shared
transport and budget service above.

## Compatibility and integration

Keep the existing offline adapter for foundation tests. Introduce a versioned,
backward-compatible shared transport and compose it centrally only after its
security and spend tests pass. Extend shared typed failure codes or carry a typed
research outcome so the API does not flatten rate limits/partial coverage into an
internal error. Lane B's source-specific normalizers and reviewed public plans can
then be reused without changing model/configuration identity semantics.

Also add a shared transaction for a catalog and its rich ledger, plus any durable
refresh scheduling/negative cache. The lane currently writes the immutable ledger
first, then the immutable catalog: a crash may leave an orphan ledger. Existing
recommendation worker/CAS logic and scheduling remain integration-owned.
