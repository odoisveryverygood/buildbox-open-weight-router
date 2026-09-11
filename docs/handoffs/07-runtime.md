# 07 — Runtime lane handoff

September 8, 2026.

**Offline lane checks: PASS. Full requested runtime milestone: PARTIAL / NOT
RELEASE-READY. Live adapters tested: NONE. Integrated/deployed: NO.**

The frozen upgrade contracts are substantially narrower than the runtime prompt.
Working implementation is delivered within the permitted paths; unsupported work
is not hidden behind an architecture-only answer or claimed as completed.

## Identity and scope

- Verified upgrade base: `48ba6e2b2dc7d7d509cc68e2314c89dd5c54fec0`.
- Implementation/test/change-request commit:
  `06729065267879cbbebe57df5686d518f81b9d23`.
- Branch: `codex/router-v2-runtime`.
- Isolated worktree: `/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-V2-Runtime`.
- This handoff is a subsequent documentation-only commit. Resolve its exact tip
  with `git rev-parse codex/router-v2-runtime`; the delivery response names it too.

Read the upgrade worktree's AGENTS, requirements, contracts, TOOLS, parallel plan,
router-v2.md and handoff 06, plus shared execution/auth/storage/API/transport code,
fixtures and tests. Created the branch/worktree from the verified tip, not the
older selected internship foundation. No other worktree was edited or merged.
No contracts, migrations, generated clients, lockfiles, studio, intelligence,
research, company corpus, root configuration or deployment files were changed.

## Implemented public entry points

All runtime code is under `router/backend/buildbox_router/gateway/`:

| Module | Delivered behavior |
|---|---|
| `keys.py` — ApplicationKeys | Independent random app keys; PBKDF2 salted verifiers only; once-returned issuance secret; expiry/revocation/tenant/scope checks; fresh metadata rechecks; fixed-window atomic server-configured rate cap and separately provisioned immutable key spend cap. No app-key self-issuance. |
| `preflight.py` — Authority, preflight, cost_bound | Injected canonical target/grant/credential/catalog resolvers and existing Selector port; exact immutable configuration/catalog/policy pins; hard eligibility, operator admission and data-class/credential scope; context/output envelope and supported-parameter checks; fail-closed unknown/conditional/extra pricing. No automatic quality ranking or migration. |
| `adapters.py` — TargetAdapters, SSEDecoder | OpenRouter and native cached Ollama nonstreaming adapters reuse shared protected transports. No arbitrary base URL, model download or client-created provider decision. Incremental bounded UTF-8/SSE framing parser implemented separately; it does not open a connection or pretend buffered output is streaming. |
| `service.py` — Gateway | Existing GET models/POST chat ports for the frozen text/alias subset; authorization before alias resolution; pinned stage instruction and caller-role demotion; durable idempotency, reservations, attempts/traces and uncertainty; incremental injected stream handling with explicit partial errors and no replay/fallback. Chat never calls a business tool or DAG. |
| `runner.py` — WorkflowRunner, SampleTools, render | Literal typed prompt rendering; actual predecessor output bindings; dependency-ready parallel waves; five registered text operations; tenant-scoped synthetic read-only lookup tables; human-review pause; durable stage outputs/run/usage events; stop-before-next-dispatch cancellation and persisted duplicate detection. No generated Python/shell, agents, arbitrary research fetch or side-effect tool. |

Gateway, ApplicationKeys and WorkflowRunner satisfy their existing port method
shapes. No duplicate public schemas, migrations or inference clients were added.
Internal composition helpers carry canonical records, not competing wire contracts.

### Accounting and private-data semantics

Calls reserve against the approved grant cap and, for app-key callers, the key cap.
Workflow keys reserve the whole workflow envelope before stages; stage reservations
still use the shared grant cap. Every dispatched model attempt has a durable ID and
initial/final records. Failed parallel model stages remain referenced by the run.
No automatic retries or fallback calls exist in the frozen subset. Ambiguous usage,
timeouts/cancellation retain conservative holds; overages freeze the remaining
shared budget. An interrupted upstream may still bill. No exactly-once inference
or automatic crash restart is promised.

Generic chat retains no prompts/outputs by default. With no retained output, a
duplicate request returns 409 and never redispatches. Optional chat retention and
the required sample-run checkpoint retention are explicit constructor settings,
positive and capped at 30 days. Tests use 60-second expiring outputs. Metadata
contains only canonical decision/usage fields, not raw upstream errors, prompts,
answers, secrets or private reasoning. Stored run outputs are tenant-private.

The current input bound is a conservative UTF-8 byte + framing envelope, not a
measured token count. Operational hard-cap admission requires integration approval
of the target tokenizer/framing and full price assumptions; see R7-3 below. Zero
local provider charge is not a claim of free infrastructure.

## Actual validation

Commands ran in this worktree's `router/`, unless otherwise stated.

| Command/check | Result |
|---|---|
| `UV_CACHE_DIR=.local/cache-lane7 uv sync --frozen --python /opt/homebrew/opt/python@3.12/bin/python3.12` | Isolated environment installed; no manifest/lockfile changes. |
| `npm ci --ignore-scripts` | Installed successfully. Two existing high-severity dependency advisories reported; not silently repaired outside ownership. |
| `uv run ruff check backend/buildbox_router/gateway tests/gateway` and Ruff format | Passed after fixing initial formatting/import/lambda findings. |
| `uv run mypy backend/buildbox_router/gateway` | Passed, six runtime source files. Initial five typing findings fixed. |
| `uv run pytest tests/gateway -q` | **50 passed**, two upstream deprecation warnings. |
| Final `make check` | **346 passed**, Ruff lint/format, mypy across 52 source files, ESLint, TypeScript, Vite build and canonical generated-schema/fixture drift checks all passed. |
| `git diff --cached --check` and owned-path inspection | Passed before implementation commit; only runtime/tests/lane notes staged. |
| Provider-key/private-key pattern scan over owned source/tests/notes | No matching key/private-key patterns. Synthetic credential placeholders are not real credentials. |
| `npm audit --json` | Two high entries: js-yaml and dependent @redocly/openapi-core; GHSA-2883-xcg3-v3hh. Integrator lockfile action required. |

New tests cover SDK-shaped subset requests through the existing HTTP app, Bearer
verification, alias scoping/disable, injected SSE frames and HTTP encoding, UTF-8
fragmentation/comments/terminal/usage frames, HTTP-200-style errors, malformed and
truncated SSE, post-delta partial failure, unsupported rich chat inputs, prompt
literal substitution, no default content retention, credential/grant/context
unknowns, pricing units/components, current OpenRouter control payloads, local
digest/transport behavior, concurrent caps, revocation/rate-limit persistence,
timeouts, cancellation, in-progress and completed duplicate runs, no-model parallel
DAGs, predecessor-output propagation, human pause and event replay. A child Python
process independently reopened the SQLite database and verified request/attempt
persistence. Ordinary parent tests deny network sockets.

The HTTP success test explicitly injects **synthetic contract-test admission**;
normal HTTP composition continues to reject synthetic operational admission. It
is software boundary verification, not a real provider result. No browser/UI test,
PostgreSQL runtime test, hosted/local target call, model-quality benchmark, strict
JSON repair, tool-call round trip or live network SSE test is claimed executed.
Existing Starlette/httpx and AnyIO deprecation warnings remain.

## OpenRouter documentation and actual adapter status

Current official pages were read directly, without broad research or billable
inference/search. Provider requests pin one endpoint tag in `only`/`order`, disable
fallbacks, require parameter support, deny data collection, request ZDR and set
prompt/completion price ceilings. They never use openrouter/auto. Buildbox selects
the pinned configuration; OpenRouter still supplies upstream hosting/dispatch and
self-reported serving metadata. A returned provider name is not independent proof
of exact endpoint or weights revision. [Provider routing documentation](https://openrouter.ai/docs/guides/routing/provider-selection).

The incremental parser handles comments/fragments and detects top-level error
events. Runtime stream failures do not become successful answers merely because
HTTP is 200; exposed output is not replayed through another model. [Streaming
documentation](https://openrouter.ai/docs/api_reference/streaming).

| Adapter | Implemented | Live status |
|---|---|---|
| OpenRouter target nonstream | Shared guarded HTTPS transport, operator secret resolver, pinned policy parameters; offline request/response tests | **NOT LIVE-TESTED**; no target grant/key/spend approval supplied or inferred. |
| Native Ollama target nonstream | Existing fixed loopback transport, cached tag/digest check, no pull/cloud model; offline tests | **NOT LIVE-TESTED**; earlier planning permission is not target permission. Not a second OpenAI-compatible provider. |
| Network streaming | Incremental decoder and injected Gateway stream orchestration only; default `streaming_enabled=False` | **BLOCKED on shared transport**; no buffered completion fallback. |
| Direct provider / configurable local OpenAI-compatible endpoint | Not representable by current approved deployment/credential contract | **NOT IMPLEMENTED / NOT TESTED**. |

No credential discovery, copied session tokens, provider purchases, model downloads,
cloud resources, deployment, production activation, push or paid inference occurred.
No new Drive/private-doc retrieval, Bright Data/Exa call, cloud database access or
Vercel action was needed. Local Git/shell, package/test tooling and direct official
documentation reads were the tools used this lane; previous connector availability
in TOOLS.md is not represented as newly verified runtime access.

## Blocking compatibility limits and requests

Read [exact change requests](../change-requests/lane-7/runtime-contract-gaps.md).

1. **R7-1:** Shared guarded streaming, pre-header admission/open, disconnect
   propagation and final actual-cost/provider observation. Frozen stream usage
   stays uncertain. No network SSE service is marked complete.
2. **R7-2:** Tool calls/tool_choice, strict JSON formats/repairs, direct configuration
   addressing, session pins/fallbacks and quality/balanced/cost-conscious variants.
   Shared schemas explicitly reject them; the lane does not invent replacement
   contracts or unsupported ranking confidence.
3. **R7-3:** Administrator-approved direct/local OpenAI-compatible endpoint records,
   fresh target lookup and target-specific token/price envelopes before live use.
4. **R7-4:** Authenticated key issuance/revocation HTTP/product flow and canonical
   persisted per-key rate metadata. Server methods exist, product route does not.
5. **R7-5:** Existing worker/composition hookup, atomic multi-record checkpoint
   recovery, latency/reason fields, disconnect-aware contexts and aggregate actual
   comparison orchestration. Runner submit currently awaits a bounded run inline;
   it is not a new asynchronous durable-job platform. Events are replay snapshots
   suitable for polling, not an indefinitely subscribed live event bus. Interrupted
   running requests cannot redispatch and need operator/integrator reconciliation.
6. **R7-6:** Review/fix the existing npm advisory through the integration-owned lockfile.

## Integration instructions (not performed)

Start with this branch's implementation commit and handoff on top of the verified
upgrade base. Do not merge the other lane into this worktree. Review the requests
above before expanding any canonical interface.

1. Bind `Authority` to fresh server-owned canonical target, catalog, RuntimeGrant
   and ProviderCredentialReference resolvers and the approved existing Selector
   implementation. No browser/grant-creation route or copied Codex credential.
2. Instantiate `ApplicationKeys` against shared SandboxStorage, `TargetAdapters`
   with an authorized server secret resolver, and `Gateway`. Keep real streaming
   disabled until R7-1 lands and its transport/security tests pass. Configure
   retention explicitly; keep normal store `offline_contract_test=False`.
3. Instantiate `WorkflowRunner` with approved tenant sample tables only. Inject
   these ports through the existing `create_app(..., execution_services=...)`
   boundary after supplying the still-missing actual ComparisonPort. Preserve
   existing studio auth and add the reviewed key-product flow. Default app wiring
   was intentionally not edited and still returns runtime-unavailable without injection.
4. Complete shared worker/recovery integration, canonical client regeneration if
   contracts change, and full API/studio acceptance. Sample fixtures and fake
   adapters are not operational admissions or a second live provider.
5. Request a grouped operational approval before any live smoke: exact artifact /
   revision / endpoint, separate credential reference, data class / egress /
   retention, capability/license/privacy evidence, token/call/deadline bounds and
   maximum spend. Live inference and production routing remain unapproved.

Changed files: six `gateway/` modules; `tests/gateway/__init__.py`, conftest and two
test modules; the lane-7 change-request document; this handoff. No shared or sibling
implementation was changed. No parallel lane was launched, waited upon or merged.
