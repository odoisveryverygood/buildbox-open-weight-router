# Lane 8 — exact integration requests against Prompt 6

Base: `48ba6e2b2dc7d7d509cc68e2314c89dd5c54fec0`. No shared files changed.
These are proposals, not new endpoints implemented by the studio.

## 1. Selection/edit authority and executable bindings

`planning_contracts.PlanInput` / `TargetRequirements` have no per-stage pins,
exclusions, API-only restriction or priority fields. `intelligence/**` is read-only.
“Keep the research model but make extraction cheaper” can currently be preserved
as a clarification note, not enforced as an edit. Add a canonical edit proposal
contract with exact base version, stage-scoped constraints and a server-generated
diff; confirmation creates a new PlanVersion and reruns authoritative selection.
Test: preserving a pin must be hard-gated, not a prose suggestion; exclusion must
remove the candidate; unsupported or ambiguous edits must ask, not guess.

The deterministic interpreter emits `outputs=("text",)` but
`ExecutablePolicy.executable_bindings` requires code `text -> result:text`. Lane 8
offers a confirmed graph rename; integration should align the planner's output
binding contract. Existing fixture examples also have missing bindings. Full
arbitrary-task interpretation remains dependent on the approved interpreter,
not on a new browser LLM path.

## 2. Discovery versus eligibility versus callable connections

`PlanningResult.research` exposes the retained ledger, but there is no independent
catalog list/get/diff/refresh HTTP endpoint or public runtime configuration listing.
The current runtime metadata job only fetches its fixed repository; deterministic
no-model planning bypasses catalog research entirely. Add tenant-authorized reads
of public snapshot IDs and configuration/admission eligibility, with safe provider
connection status (no credential values), effective restrictions and dates.
Expose bounded refresh through the existing jobs, accepting only public candidate
IDs and missing/stale fields. Never accept private task text as a search query.

Lane-local `research.review` supplies read-only canonical Issue diagnostics for
relevant stale fields and snapshot changes. It is tested, **not composed into an
HTTP route**. Existing source acquisition/parsers/guards remain unchanged. A new
snapshot must never move an enabled alias. Test no-data/no-results versus unknown,
stale endpoints, conflicting claims, and exact configuration/artifact identity.

## 3. Comparison/import completeness

The frozen `execution_api.compare` requires every policy to be enabled before
submission. This allows provisional sandbox testing but makes compare-before-route
a preparation-only experience. Add operator-authorized, bounded diagnostic
admission for comparison that does not create an externally callable alias.
Preserve all privacy/license/access/capability/budget gates, not quality prerequisites.

`ImportedSample` forbids split, rubric, tool schemas and tenant fields. Add canonical
dataset/split provenance (tuning versus immutable holdout), rubric version and
optional inert tool-schema declarations, plus redaction/consent records. The UI
currently rejects unsupported import fields and labels all comparisons exploratory.
Example that correctly fails today:

```json
{"inputs":{"text":"Synthetic"},"split":"holdout","tool_schemas":[]}
```

`ComparisonCell` has output/usage references but no timing, rubric/validation
results or failure detail. Add run-linked TTFC/completion durations, validation
results and safe error references; never turn missing metrics into zero. Test
partial cells, uncertainty, retention expiry and untrusted output rendering.

## 4. Activity, keys and operational control

Only exact-ID reads exist. Add cursor/date/route-filtered tenant lists for plans,
policies/transition history, aliases, runs, attempts, comparisons and aggregated
reconciled usage. Existing canonical `RunAttempt` needs an authenticated read
endpoint. Add key create/revoke metadata routes through `ApplicationKeyPort`, a
secure issuance flow and safe connection summaries through credential references.
No browser provider-key storage; application-key scopes/budgets stay server-owned.

Current UI loads exact versions, issues CAS enable/disable transitions using an
operator-issued admission ID, and can explicitly re-enable a still-valid old
version without repinning aliases. It cannot issue its own admission or verify a
connection from catalog metadata. Runtime composition stays Lane 7/integration-owned.

For durable recovery after a timed-out submission, add tenant-scoped lookup by
idempotency key/request ID. The studio prevents automatic retry of an uncertain
run, but a lost response currently cannot be recovered by a list/request lookup.
Add a transactional batch import or idempotent import behavior to improve partial
batch recovery; current imports report saved row IDs and never pretend atomicity.

## 5. Dependency advisories and migration impact

`npm ci --ignore-scripts` succeeded but `npm audit --json` reported two high
development-chain findings: `@redocly/openapi-core` via `js-yaml`, including
GHSA-2883-xcg3-v3hh (CPU denial of service on YAML merge sources). The frozen root
lockfile is unchanged. Integration should update the affected dependency and
regenerate/check canonical output. `npm audit --omit=dev` is recorded separately
in the handoff; no automatic audit fix was run.

All requested record additions require integration-owned Pydantic/OpenAPI/client
generation; dataset/consent/history additions likely need additive persistence
migrations. Preserve v1 records, v2 pinned policies and old source observations.
No lane-local replacement schema, migration, API composition or provider transport
was introduced. Ordinary tests remain offline and synthetic/public.
