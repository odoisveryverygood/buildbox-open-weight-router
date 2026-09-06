# Lane B research implementation

The mapped lane owns this directory and `tests/research/`. Shared contracts,
composition, worker, transports and the intelligence lane are unchanged.

`PublicResearch` implements the frozen `ResearchPort` and `CatalogPort` using
an explicitly supplied public plan. `SnapshotCatalog` pins one immutable catalog
for a recommendation. `RecordedSources` implements `SearchPort` with retained
public metadata; it is an offline adapter and makes no network calls.
`RuntimePublicSearch` fails closed pending shared transport and authorization.

## Roles and authority

1. `ArtifactDiscovery` validates publisher/repository/revision, listed weights,
   declared license and access conditions from structured Hugging Face metadata.
2. `CapabilityEvidence` extracts one reviewed table cell for an exact subject from
   a pinned publisher card, preserving missing methodology and measurement dates.
3. `DeploymentEvidence` requires an explicit repository-to-OpenRouter mapping and
   records each provider endpoint separately, including its limits, declarations,
   price components and restrictions.

The artifact job precedes the two independent downstream jobs, which run
concurrently. Roles use deterministic parsing with versioned parsers. No model
assistance is needed, no prompt/key is required, and the default token budget is
zero. Adding model assistance requires the integration-owned bounded inference
contract; source prose cannot choose tools or change permissions or budgets.

`Limits` bounds total calls, reserved dollars, tokens, retries, response bytes,
search results, per-call time and overall time. One locked ledger is shared by all
jobs in one run. A timeout retains its reservation and is never retried while a
late call could still run. Cancellation prevents publication; late replay results
have no write authority. Durable cross-process spending and transport cancellation
are shared integration requirements, not claimed capabilities of this lane.

## Evidence and catalog semantics

`records.py` contains private ledger records that compose canonical `ModelArtifact`,
`Evidence` and `Fact`; it does not replace the public schema. `observed_at` and
`expires_at` are retained per field, with configurable freshness policy. Publication
validates proposals against original captured bytes and reviewed locators. Source
conflicts and missing coverage remain explicit. No averaged ranking is produced.

The ledger retains minimal public fields/excerpts and their source locators, with
canonical evidence plus benchmark name/version/split, raw metric/unit, method,
sample size, publication/test dates and limitations. A publisher-reported metric
is not a Buildbox measurement. An endpoint revision may be unknown even when its
publisher repository mapping is known. Gated access is distinct from a weight
listing, and license metadata is not a reviewed/accepted license agreement.

Endpoint prices retain raw decimal strings and units. Input/output token rates
can be displayed per million tokens; request/image/unknown-unit charges are not
converted to token prices. Conditional price rules are retained, not silently
evaluated. A cost per 1,000 tokens remains unknown without a declared workload mix.

The public capture has no prompt/harness bindings. Its canonical snapshot contains
eight real artifacts and zero selectable configurations. One provider endpoint
declaration remains in the ledger. `ConfigurationBinding` is an explicit
integration input; it never comes from a source page. Bound projections retain
unknown workload latency/cost. Gated/unknown access cannot be projected as cleared.

Public sources and tenant-private evaluation data remain separate. The workflow
argument is not serialized, summarized, logged, or sent to research tools. A
reviewed public plan supplies identities and source locators independently.

## Cache and persistence

Fresh claims with matching plan/source/policy reuse cached results. Missing or
expired sources are revisited only in the relevant role. Replaying old captures
does not reset their timestamps. Refresh produces a new content-addressed catalog;
previous catalog/ledger rows remain immutable using the shared `StoragePort`.

The ledger is written before the canonical snapshot. The frozen port has no
transaction covering both objects: a crash can leave an orphan ledger but cannot
publish a catalog before its ledger. Identical content is idempotent; conflicting
stored content is rejected. The fixed public storage namespace is not identity or
authentication. Shared/live application modes remain disabled by foundation.

## Reproduce the public replay

From `router/` after `make setup`:

```sh
UV_CACHE_DIR=.local/cache-lane3 uv run python -m buildbox_router.research \
  --sources tests/research/public/sources-2026-09-06.json \
  --plan tests/research/public/plan-2026-09-06.json \
  --database .local/lane3.db --output .local/lane3-public-replay
```

This command uses local SQLite and retained public sources only. It does not
change application composition, invoke a model, execute tools, or activate routing.
The source acquisition audit is `tests/research/public/README.md`; shared requests
are in `docs/change-requests/lane-3/` at the repository root.
