# 06 — Workflow-aware sandbox upgrade base

**Parallel-ready: YES for independent Lane 7/8 implementation against the frozen
interfaces. Runtime/product upgrade complete: NO. Lanes launched: NO.**

## Identity

- Branch: `codex/router-upgrade-base`.
- Worktree: `/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-Upgrade`.
- Exact audited base: `a3f8c28ed42d461ed570800b7addcd2a4c487f36` from
  `codex/router-integration`, not the older selected foundation checkout.
- Main implementation: `574a6a1269a298c2d65ba1329cf5aaad0e184b15`.
- Final tested code including the shared `/v1` dev proxy:
  `2c5cad8c6a603cf0c49fbbeb48de728accfd330b`.
- This handoff is a subsequent documentation-only commit. Resolve the common
  lane starting tip using `git rev-parse codex/router-upgrade-base`; the final
  delivery also names it. Do not start from just the earlier code commit.

The old foundation/intelligence/research/integration branches and worktrees were
not changed. No lane worktrees were created or delegated. No remote exists and
there was no push, deployment, protected-main change or Radar-project modification.

## Actual audit, not assumed milestone completion

Read root AGENTS, requirements/contracts/tools/parallel plan, handoffs 01–04, actual
backend/UI/runtime/research/storage code and tests. Available refs contain no
separate milestone-05 handoff or implementation commit; completion cannot be
inferred from the statement that five milestones were attempted.

The native Google Doc was reread with the Drive skill, read-only. Its original
research assignment and subsequent product context were distinguished from the
user's new sandbox engineering scope. No private document text was added to the
repository or sent to search/model services.

| Area at audit | Evidence and status |
|---|---|
| Describe / processing controls / planning | Working local app. Browser extraction example saves a real persisted planning job and synthetic configuration mapping. |
| Clarification / edits / versions | Code/tests and browser correction→version 2→reload preserve answers and exact versions. Graph editor exists, but sample bindings are visibly unspecified. |
| Research / catalog | Existing 8-release public snapshot, typed provenance and bounded jobs work offline. Opt-in official metadata runtime code is present; no new metadata call this milestone. No complete real target configuration is verified. |
| Inference | Existing local/Ollama planning adapter and prior run evidence preserved. Audit UI correctly shows local model unconfigured. Hosted OpenRouter remains offline-tested, not live-verified. Neither is a completed target router. |
| Comparison / evaluation | Existing comparison is synthetic configuration rationale. No actual output comparison or workload-quality validation; evaluation remains not run. |
| Export / execution | Browser downloaded the actual v1 synthetic policy: draft, active=false, production_write=false, no execution tools. No gateway, application-key runtime or workflow runner existed before upgrade. |

Browser used actual ports **5196/8026**, a separately migrated
`router/.local/upgrade-audit.db`, and session `upgrade-base`. Saved plan
`92c25ac0306347a0a672f4f92aeeb2b9`, version 2, survived migration/restart/reload.
Screenshot: `router/output/playwright/upgrade-base-audit.png` (ignored, inspected).
Downloaded policy: `.playwright-cli/buildbox-v2-inactive-policy.json` (ignored,
inspected). Final checked browser console: **0 errors / 0 warnings**.

## Shared implementation delivered

- Additive execution-schema 2.0 contracts compose canonical v1 workflow/config/fact
  and rich endpoint types, not duplicate contracts. Typed complete bindings,
  versioned literal prompts, approved deterministic operations, tool allowlists,
  call/token/cost/time bounds and stop conditions are validated.
- Draft/sandbox-enabled/disabled transitions are append-only with compare-and-swap
  sequences. Policy content is immutable. Tenant-local aliases pin exact policy
  version + LLM stage + configuration and cannot be repointed.
- Admission distinguishes untested provisional quality from mandatory server-side
  privacy/license/access/capability/authorization/spending checks. Synthetic guard
  fixtures cannot activate through normal HTTP composition. There is no public
  admission/grant provisioning endpoint and no production state.
- Application-key scope/expiry/revocation metadata and salted-verifier persistence;
  separate provider credential references and target-sandbox grants. Actual key
  authentication/issuance and provider credential resolution belong to Lane 7.
- Chat Completions-compatible **subset**, model listings, responses/chunks/errors,
  run attempts, usage reconciliation, request traces, run events, comparisons,
  prompt revisions, imports and expiring outputs are centrally typed/generated.
- Working studio HTTP persistence and explicit `ExecutionServices` composition
  hook. Default execution/comparison ports are uninstalled and return 503. One
  chat call dispatches only GatewayPort; a distinct WorkflowRunnerPort handles
  `/api/sandbox/runs`. Offline injection tests prove the chat path does not invoke
  a workflow DAG. These injected responses are labeled synthetic test data.
- Revision 3 adds tenant-local immutable sandbox metadata, transition heads,
  request idempotency/CAS, budget/reservation accounting, key verifier storage and
  separately expiring private payloads. Unknown usage stays unknown; conservative
  holds survive failure/cancellation; overage freezes the approved remaining cap.
- Runtime/public HTTP guard, local planning adapter, existing UI flow, selection,
  research implementations, manifests and lockfiles remain unchanged. Vite now
  proxies `/v1` as well as `/api`, so lanes do not need a shared config change.

## Executed validation

Commands ran from this worktree's `router/` unless stated otherwise.

| Check | Actual result |
|---|---|
| `UV_CACHE_DIR=.local/cache-upgrade uv sync --frozen --python /opt/homebrew/opt/python@3.12/bin/python3.12` and `npm ci --ignore-scripts` | Installed isolated dependencies; no manifest/lockfile changes. Existing Python 3.12 pin retained. npm audit reported 0 vulnerabilities; ESLint deprecation notice remains. |
| Baseline `make check` at audited base | **250 tests passed**, lint/format/types/build/generated drift passed. |
| `uv run python scripts/generate_sandbox_fixture.py` | Generated canonical synthetic shared policy fixture, no model outputs/admissions. |
| `make generate` | Generated OpenAPI/TypeScript from canonical shared schemas, including contract-only SSE/trace records. |
| Final `make check` (after `/v1` proxy change) | **296 tests passed**; Ruff lint/format, mypy (46 source files), ESLint, TypeScript, Vite build, schema/type and fixture drift all passed. |
| Shared upgrade tests | 46 new cases cover typed bindings, incomplete prompts/operations, hard unknown/false gates, synthetic admission denial, CAS transitions, alias isolation/no repin, key scoping/durable revocation, request replay/no redispatch, budget concurrency, immutable snapshots, private retention, real studio HTTP persistence, chat dispatch isolation, SSE encoding and schema references. |
| SQLite | Clean revision 3, explicit revision-2 upgrade/rerun with old records preserved; actual audit DB migrated and browser reloaded. |
| PostgreSQL clean + prior-flow regression | `scripts/check_postgres.py` passed migrations/rerun, API/worker/export, staleness, immutable records and concurrent planning approval cap. |
| PostgreSQL revision-2 → revision-3 | `scripts/check_upgrade_postgres.py` passed preservation/rerun, policy/alias immutability, tenant isolation, disabled transition and concurrent sandbox cap. |
| Browser after changes | Saved planning state reload and actual inactive download passed; no console errors/warnings. |
| Real local `/v1` dev proxy | GET models returned typed 503 runtime_unavailable; POST with unsupported `n` returned typed 400 unsupported_parameter, not HTML or fake output. |
| `git diff --check`, preserved-path diff, credential-pattern scan | Passed; no changes to old intelligence/research/planning transports/UI flow or manifests/lockfiles; no matching provider-key/private-key patterns in new source/tests/docs. |

Two existing upstream Starlette/httpx/AnyIO deprecation warnings remain. Initial
formatting issues were corrected and full checks rerun. An initial screenshot
write needed its output directory; capture then succeeded. No failed or unexecuted
live-model/quality test is counted as passed.

PostgreSQL was an independently initialized UTF-8 local cluster in
`/tmp/buildbox-upgrade-pg.Juqbk3/data`, loopback **55496**; final checks used fresh
`upgrade_final` and `upgrade_forward_final` databases, not a shared database:

```sh
ROUTER_DATABASE_URL=postgresql+psycopg://buildbox_upgrade@127.0.0.1:55496/upgrade_final uv run python scripts/check_postgres.py
ROUTER_DATABASE_URL=postgresql+psycopg://buildbox_upgrade@127.0.0.1:55496/upgrade_forward_final uv run python scripts/check_upgrade_postgres.py
```

The test cluster was stopped after verification; data was not deleted. The audit
UI/API remain on 5196/8026 for review. No existing 8000/5173 service was changed.

## Tools, approvals and remaining blockers

Current inventory is in `docs/TOOLS.md`. Drive and GitHub read connectors worked
(GitHub returned no repositories). Bright Data/Exa tools were discovered, not called
for search/extraction. Vercel project reads returned 12 projects, none Buildbox-named.
No selected/approved cloud database exists in this app; native PostgreSQL was
reused for verification rather than provisioning Neon/Supabase. No credentials
were located/copied and no balance, account, purchase or deployment was assumed.

Remaining work is explicit, not hidden behind the parallel-ready label:

1. Lane 7 must implement real target inference/gateway, key auth, sample runner,
   tool dispatcher, durable runtime orchestration/accounting and cancellation.
   Default composition deliberately performs none of those calls.
2. Lane 8 must build the stage/prompt/compare/import/sandbox/run UI and source-backed
   target configurations. Current production recommendation restrictions stay
   intact; testing candidates are separately provisional.
3. No operational admissions/grants/keys or verified target configuration are
   seeded. No real target inference/output comparison or quality validation ran.
4. Request one grouped operational approval before live target tests: exact model
   artifact/revision, endpoint, independent credential reference, permitted data
   class/privacy/retention, license/capability evidence, calls/tokens/deadlines and
   total spend cap. A pre-existing planning permission is not this approval.
5. Shared/public deployment remains gated on TLS, identity/secret operations,
   encrypted retention/backups and final integration/security review. The local
   payload store is not represented as managed encryption-at-rest.

## Lane instructions and changed paths

Read `docs/upgrades/router-v2.md` in full. It freezes the actual paths, ports,
contracts, HTTP semantics, admission/quality boundary, idempotency/accounting,
private retention and exact ownership. It assigns separate worktrees, ports,
databases and caches without creating or launching them. Shared changes go in
lane-local change requests; neither lane edits generated code, schemas, migrations,
shared transports/composition, manifests or the other's implementation.

Changed paths: root `.gitignore`/`AGENTS.md`; requirements/contracts/tools/parallel
docs; `docs/upgrades/router-v2.md`; router shared `execution_*.py`,
`openapi_schema.py`, `api.py`, migrations; central generation/check scripts,
PostgreSQL upgrade check; shared contract fixtures and integration tests;
generated OpenAPI/TypeScript and `web/vite.config.ts`; this handoff. No unrelated
internship corpus/deliverable, old lane checkout, protected main or Radar path was
modified. **Start neither lane until the user explicitly requests it.**
