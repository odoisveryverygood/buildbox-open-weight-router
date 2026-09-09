# 07B — integrated runtime handoff

September 8–9, 2026. **Integrated offline milestone: complete for the documented
subset. Production readiness / live inference: NOT verified.**

The runtime is no longer an isolated injected lane. The application installs its
real runtime ports from an explicitly approved operator registry; its existing
worker claims durable workflow jobs, and Prompt 8 reads actual saved runtime state.
Verification used synthetic HTTP/recorded providers, never fabricated live evidence.

## A. Existing Prompt 7 code reused

Worktree: `Buildbox-Router-Integration`; branch: `codex/router-integration`.
No edits in either lane worktree, protected main, research corpus or another project.

- Prompt 6 lane base: `48ba6e2b2dc7d7d509cc68e2314c89dd5c54fec0`.
- Preserved Prompt 7 implementation: `06729065267879cbbebe57df5686d518f81b9d23`;
  preserved tip: `027b950835eea9007dc8e4561b030eaea1772590`.
- Preserved Prompt 8 implementation: `c61569b8467ae279d262506039cecc57cbcbaca4`;
  preserved tip: `fe996d846499581a88c01e0f8c67f87a2285eb92`.
- Integration history merge: `4e5d47113ccd2617d896d85f0ace4eef78c948fd`.
- **7B implementation: `57b6cf459d370e5892d11d4100f56a63d7e2b54d`.**
- This handoff and the final HTTP/SSE assertion strengthening are a subsequent
  local commit. Resolve its exact tip with `git rev-parse codex/router-integration`;
  the final response supplies that hash. Do not start from the old lane tip alone.

Reused Authority, selector, alias/version admission, application-key PBKDF2 and
revocation, reservation/reconciliation, nonstream OpenRouter/native local adapter,
SSE framing logic, WorkflowRunner's dependency frontiers, operations, sample tools,
human pauses/checkpoints and existing worker. Extended those paths instead of
creating another gateway app, worker platform, inference client hierarchy or schema.
The old lane handoffs remain historical evidence, not edited claims of completion.

## B. Central shared changes

The pre-implementation code-path/interface audit is
`docs/handoffs/07b-runtime-unblock-plan.md`.

| Central boundary | Implementation |
|---|---|
| Canonical wire and policy contracts | Typed tools, tool history/calls/deltas, bounded JsonSchema/response formats, stream terminal observation, approved endpoint reference, policy variant/fallback/restriction fields, per-attempt latency, key issuance and runtime status. No duplicate workflow/catalog types. |
| Streaming transport | `inference_transport.py`: approved endpoint IDs, pinned DNS/TLS, explicit loopback exception, no redirects, bounded timeout/bytes and cancellation cleanup. `provider_contracts.py` validates upstream frames; `stream_validation.py` reconstructs bounded terminal output. |
| Gateway integration | Existing service preflights every primary/fallback, reserves each attempt, validates tools/JSON, records observed cost even on invalid nonstream output, and refuses model substitution after any exposed delta. HTTP prefetches first event before headers and watches disconnect. |
| Policy variants | `execution_policy.py` uses existing selector and pinned catalog to create new drafts; no alias mutation. Quality/balanced deliberately share an uncalibrated rule in absence of comparable workload evidence. |
| Product composition | `runtime_contracts.py` and `execution_composition.py`: typed operator records and approved secret references, separate from session connectors/planning permissions. Explicit live+shared mode required; no automatic live-to-fixture fallback. Normal authority verifies the registry against the immutable owned planning catalog. |
| Persistence / worker | Revision 4 durable queue/lease. Atomic request+queue+expiring input admission; stale leases become uncertain, never retry permission. Existing `worker.run_once` invokes `QueuedWorkflows`, which reuses WorkflowRunner. Key creation plus its budget is atomic; immutable cap replacement is rejected. |
| Studio / comparison | Real key/status, workspace workflow runs, exact run attempts, traces and outputs. Comparisons use the same worker jobs and actual per-attempt reservations, not fake aggregate usage. UI consumes generated contracts and preserves Prompt 8's existing planning/import/draft flow. |

Execution-schema 2.0 changes are additive; old policy digest defaults are retained
and tested. The database upgrade preserves existing records. OpenAPI, TypeScript
and the shared synthetic policy fixture were regenerated centrally. No live model
entry, credential, grant or admission is automatically seeded.

Changed code is in shared `router/backend/buildbox_router/{execution_*,config.py,
api.py,worker.py,migrations/,inference_transport.py,provider_contracts.py,
json_contracts.py,runtime_contracts.py,stream_validation.py}`, preserved `gateway/`,
studio components/model helpers, generated schemas/fixture, gateway/integration
tests and PostgreSQL/browser checks. Root instructions, tools/upgrades docs and
`.env.example` explain the new boundary. Full file list:
`git show --format= --name-only 57b6cf459d370e5892d11d4100f56a63d7e2b54d` (47 files).
Intelligence/research implementation, root manifests and lockfiles were unchanged.

## C. Previous blockers

| Blocker | Status | Evidence / remaining boundary |
|---|---|---|
| Network streaming | **RESOLVED for supported subset** | Actual HTTP/SSE loopback transport + authenticated `/v1` product stream; split UTF-8/TCP frames, coalesced events, usage, midstream errors/cancel/timeout and before/after-commit fallback tests. Real commercial-provider streaming is not claimed. |
| Tool / structured JSON chat | **RESOLVED for supported subset** | Canonical request/response/delta schemas, returned calls and matching histories, strict output validation; no chat tool execution. JSON+stream, JSON+tools and unsupported schemas/parameters reject before dispatch. |
| Policy variants | **RESOLVED, heuristic only** | New draft quality/balanced/cost-conscious variants; fixed primary/per-stage configuration, bounded explicit fallbacks and restrictions, immutable version/status. No validated quality ranking or automatic activation. |
| Second compatible provider | **PARTIAL: implementation and fixtures complete, live unverified** | Administrator-approved direct/loopback endpoint adapter and genuine HTTP fixture tested. No second real provider/configuration was available. **LIVE SECOND PROVIDER = UNVERIFIED.** |
| Product / worker wiring | **RESOLVED** | Product auth/key → alias/version → selector/authority → adapter → response/stream → trace/accounting; workflow HTTP → atomic queue → existing worker → stages/checkpoint/pause → UI/reload. No isolated alternative application route. |

## D. Commands and actual results

Commands below ran from the integration worktree's `router/`.

| Command / check | Result |
|---|---|
| `make generate`; `uv run python scripts/generate_sandbox_fixture.py` | Canonical OpenAPI/TS/fixture generation succeeded; fixture still explicitly synthetic. |
| Final `make check` | **399 backend tests passed**, 2 pre-existing Starlette/httpx/AnyIO deprecation warnings; Ruff lint/format, mypy (62 source files), ESLint, TypeScript, Vite production build and generated drift passed. |
| `uv run pytest tests/gateway -q` | **94 passed**, including all original 50 lane tests and 44 additional 7B cases. |
| Final strengthened `uv run pytest tests/gateway/test_unblock.py -q --maxfail=1` | **44 passed**, including authenticated product → real synthetic HTTP SSE and preheader upstream error → JSON 502. No implementation changed after the full check. |
| `node web/tests/unit.cjs` | **14 frontend unit checks passed**. Existing tests were retained; additions only changed expectations where canonical support genuinely changed. |
| `uv run python scripts/check_generated.py` | OpenAPI/TS and canonical fixture drift clean after final generation. |
| `scripts/check_upgrade_postgres.py` | Fresh isolated UTF-8 PostgreSQL: v2→v4, rerun, old records, policy/alias immutability, tenancy and concurrent cap passed. Additional SQLite v3→v4/legacy-digest test passed. |
| `scripts/check_postgres.py` | PostgreSQL clean migration/rerun, planning API/worker/export, immutable versions/staleness and concurrent approval cap passed. |
| `uv run python -m tests.gateway.pg_smoke` | PostgreSQL HTTP app-key auth → atomic durable queue → worker → checkpoint; duplicate submission/no redispatch, exact attempt query/trace/usage and ownership passed. Recorded inference only. |
| Playwright `web/tests/browser_live.js` | Prompt 8 actual browser regression passed: planning/edit version, draft/save/reload, disabled route, import, missing-comparison error, public *saved* evidence snapshot and mobile layout. No new public catalog fetch. |
| Playwright `web/tests/browser_runtime.js` | Actual Basic-authenticated app → queued workflow → existing worker → synthetic HTTP model → human pause; output, attempt/usage/trace metadata, reload and mobile layout passed. Runtime state visibly `synthetic_test`, live_verified=false. |
| `git diff --check`, preserved implementation path diff, credential-pattern scan | Passed. No provider keys/private keys or session credentials found in changed source/docs; runtime/studio lane refs unchanged. |
| `npm audit --omit=dev` | 0 production dependency vulnerabilities. |
| Full `npm audit` | **2 existing high-severity development advisories**: `@redocly/openapi-core` and `js-yaml`. Not silently hidden or fixed with unrelated lockfile churn. Address before using the generation toolchain on untrusted specs/deployment hardening. |

PostgreSQL used task-created `/tmp/buildbox-7b-pg.Bq6xTo/data`, port **55439**;
no shared/production database. Commands:

```sh
ROUTER_DATABASE_URL=postgresql+psycopg://127.0.0.1:55439/buildbox7b_upgrade_utf8 uv run python scripts/check_upgrade_postgres.py
ROUTER_DATABASE_URL=postgresql+psycopg://127.0.0.1:55439/buildbox7b_clean_utf8 uv run python scripts/check_postgres.py
ROUTER_DATABASE_URL=postgresql+psycopg://127.0.0.1:55439/buildbox7b_runtime_final uv run python -m tests.gateway.pg_smoke
```

Initial failures were corrected rather than counted as passes: stale rejection
tests for now-supported fields; revision-3 expectation changed to revision 4;
native Ollama recorded-stream fixture replaced by an explicitly capable hosted
fixture; incremental decoder delivery bug; initial PG SQL_ASCII database replaced
by fresh UTF-8 databases; browser test factory moved its fixture setup off the
running event loop. A transient wrong Vite CLI root/port was stopped and corrected.
No existing service was stopped for those corrections.

Browser checked **5199/8029**, session `buildbox7b`, newly created temporary DBs.
Final run `bd48a1f697a1478db3f1b3028a31811e` reached **awaiting_approval** with one
actual synthetic-provider attempt; no human approval was invented. Screenshots in
`router/output/playwright/` (ignored, visually inspected):
`7b-runtime-activity.png`, `7b-runtime-mobile.png`, `7b-runtime-status.png`, plus four
Prompt 8 regression captures. Browser QA corrected the stale recent-run list after
a completed submission. Final scripts had no page exceptions or horizontal mobile
overflow; deliberately querying a missing comparison logs its expected HTTP 404.
Earlier startup errors are retained in the local log, not represented as a clean
first attempt. No newly issued secret was displayed in screenshots.

## E–F. Verified access versus fixture-only functionality

**LIVE INFERENCE NOT VERIFIED. LIVE SECOND PROVIDER = UNVERIFIED.**

After fixtures passed, the named OpenRouter/OpenAI/compatible-provider key,
runtime-registry/auth/approval and local-interpreter environment variables were
absent. No `.env` or documented default runtime-registry file existed here. This
checks the named configuration, not hidden credentials/accounts elsewhere.
No live A/B/C/D smoke request was attempted; missing authorization is not a failed
inference test. No credits/balance/account permission was assumed. **Money spent: $0.**

Verified development tools: local filesystem/Git, installed Python/Node toolchain,
native PostgreSQL, Playwright/browser, read-only official OpenRouter documentation.
Other connector availability is historical/not renewed; no Bright Data, Exa,
cloud database, Drive write, provisioning or deployment was performed. Connector
access never becomes a runtime secret or provider authorization.

Real socket transport and durable product wiring are implemented and tested, but
model responses/costs in these checks are **synthetic**. OpenRouter control payloads
were verified with recorded responses. No model quality, real price, downloaded
weights or legal suitability has been established by these tests.

## G. Compatibility limits

`docs/API_COMPATIBILITY.md` classifies every accepted parameter and rejected feature.
Most important limits: alias-only model identifiers; text/tool messages, not
multimodal; strict bounded JSON schema subset only; no JSON streaming or JSON+tools;
no n/top_p/stop/seed/logprobs/stream_options/max_completion_tokens/provider override;
native Ollama remains nonstream text-only. Unknown required capabilities/prices
block, not default to false/zero. Single-configuration aliases are required for
conversation/tool sessions; no implicit fallback-session repinning.

Runner limitations remain explicit: reviewed literal prompts, registered deterministic
text operations, allowlisted sample lookup and human pause only. No arbitrary
shell/Python, side-effectful tools, automatic human approval/resumption, GPU launch,
public tool execution or production activation. A local compatible endpoint is
not automatically treated as satisfying an imported sample's native-local-only
restriction. Comparison is exploratory outputs/usage, not quality validation.

## H–I. Integration/use instructions and remaining requests

1. Continue on the integration tip or create a new, unused worktree/branch from
   the exact final commit. Do not cherry-pick only 7B onto a lane lacking the other
   history, overwrite branch names, or move either lane's current worktree.
2. Reuse `make setup`, explicitly migrate with `make migrate`, then `make check`.
   Start the existing API and worker from the same revision/configuration.
3. For a **real** target, an operator must provide real shared authentication,
   `ROUTER_MODE=live`, a canonical private `ROUTER_RUNTIME_REGISTRY_FILE`, immutable
   owned planning catalog, current target/token-envelope and mandatory evidence,
   exact credential reference/endpoint ID, data class/privacy, grant/admission and
   spend cap. Store provider secrets only in approved server bindings. No HTTP
   grant-creation API or automatic seeding exists. Retention must be reviewed.
4. Then run the smallest authorized nonstream/stream/JSON/tool-call smoke checks;
   do not execute the returned external tool. Record served identities/usage and
   leave unknowns pending. This remains an operational authorization/verification
   request, not a missing lane-private interface.
5. Reproduce browser software checks only with the explicit test entry point
   `uv run uvicorn tests.gateway.browser_fixture:create_fixture_app --factory --host 127.0.0.1 --port 8029`
   and `ROUTER_API_ORIGIN=http://127.0.0.1:8029 ROUTER_WEB_PORT=5199 npm run dev`.
   Use the **synthetic** identity from that test helper, never real credentials.
   Playwright CLI executes `web/tests/browser_live.js` then `browser_runtime.js`.
   The helper is not a production app or a second real inference provider.
6. Before any public deployment: resolve development advisories, review TLS/auth,
   managed secrets, encrypted retention/backups, rate/admission operations and
   production security. Local DB storage is not claimed encrypted at rest.

No remaining frozen-contract request blocks the documented integrated subset.
The second-provider live check and real operational admissions remain unverified;
broader OpenAI/session/workflow features require separately scoped work. Policies
remain draft until explicit sandbox admission; no production migration, merge to
production, remote push or public deployment occurred. Task-owned test services
are stopped at handoff; local screenshots and temporary test data are retained.
