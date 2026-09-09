# 08 — Product studio / catalog lane

September 8, 2026. **Owned implementation and offline checks: PASS. Full requested
product: PARTIAL / integration-blocked. Live model execution: NOT TESTED.**

## Exact identity and ownership

- Branch: `codex/router-v2-studio`.
- Worktree: `/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-V2-Studio`.
- Verified Prompt 6 base: `48ba6e2b2dc7d7d509cc68e2314c89dd5c54fec0`.
- Implementation/checks commit: `c61569b8467ae279d262506039cecc57cbcbaca4`.
- This handoff is a subsequent documentation-only commit; resolve the final tip
  with `git rev-parse codex/router-v2-studio`.
- Runtime lane appeared during this task. Read-only `git merge-base` confirmed
  the same full base hash. Its observed tip was `027b950`; its handoff was read,
  but its code was not imported, merged, edited or launched here.

Read AGENTS, requirements/contracts/TOOLS/parallel-plan, router-v2.md and handoff
06, actual React/planning/research/execution APIs and contracts, generated types,
fixtures and tests. Preserved the existing React/Vite/FastAPI stack and design.
Only `web/src` outside generated, owned tests, research implementation/docs and
lane-local notes changed. No contracts, migrations, generated types, shared
transport/security/composition, runtime, intelligence, root manifests/lockfiles,
deployment, other worktree or internship/Radar corpus was changed.

## Delivered behavior and honest boundaries

| Area | Implemented and verified | Still missing / not claimed |
|---|---|---|
| Workflow-first journey | Existing diverse-text intake, processing/constraint form and saved plans retained; explicit plan-change diff/confirmation; stages, dependencies, missing questions, model mapping and evidence lead into Steps → Compare → Routes/run → Activity. | Arbitrary language quality is not established. Targeted natural-language edits are preserved notes, not enforced model pins. Interpreter and pin/exclusion/priority contracts are read-only/missing. |
| Executable drafts | Typed stage/prompt proposal from saved workflow and server-selected configuration; explicit deterministic operation choice; output type/advanced canonical JSON editing with presentation guard; diff and confirmation; real prompt/policy persistence; sequential new drafts reset quality to provisional; old pins untouched. | Incomplete graphs fail closed. Full output JSON Schema, automatic alternative-stack construction and new selection semantics are not invented. Advanced JSON edits are server-validated, not a client replacement schema. |
| Planner/sandbox mismatch | Browser found code output `text` versus required `result`; UI offers an explicit graph rename, confirmed and saved as a new plan version. | Canonical interpreter alignment requested from integration, not patched across ownership. |
| Model explorer | Search, declared-task/weights filters; artifact/revision versus configuration/endpoint identity; license/access provenance, modality unknowns, declared limits/parameters/privacy/restrictions, price components and units, claim/source locators, dates, benchmark methodology gaps, stale badges and conflicts. | No real callable target is claimed. Public declarations are not measured quality or license acceptance. Connection status and authoritative callable list need shared HTTP endpoints. |
| Research and refresh | Three role coverage counts plus actual persisted job progress; existing cache/opt-in controls; manual refresh proposal creates a new plan, never repins a route; in-session snapshot diff. New read-only `research.review` helpers bound stale/missing-field review and distinguish claim changes from recapture dates. | Helpers are offline-tested, not composed into a new HTTP route. Independent catalog refresh/list and durable diff history need integration. Fixed-repository runtime research was not expanded or live-called. No scheduler built. |
| Samples/imports | Text, JSON and ≤20-row JSONL, ≤64 KiB; local file size check, named inputs, recursive named-key redaction, nesting/unsafe-key/date checks, data class, consent, review and retention; real canonical imports; partial batch saved IDs retained visibly. | No automatic secret detector. Split/holdout/rubric/tool-schema fields are absent from the frozen contract and are rejected, not silently dropped. These are exploratory samples, not a registered holdout. Imported answers are not ground truth or tool grants. |
| Comparisons | 2–3 exact policy versions with disclosed settings, one selected sample set/cap, explicit cost confirmation, canonical submit/get/output calls; returned output, failed/blocked cells, usage/cost and sample count; no winner from one result. Fixture transport tests verify output rendering and no refresh redispatch. | Real ComparisonPort is uninstalled and runtime handoff also leaves orchestration pending. No live outputs, TTFC/completion timing, rubric scores, quality ranking or automatic single-model baseline generation. The UI names these gaps. Frozen API requires enabled policies; comparison-before-enable is preparation only. |
| Routes/developer | Real exact-version loading, append-only CAS enable/disable requests, operator-issued admission reference only; explicit old-version re-enable path; immutable alias create/get; cURL/Python/TS environment-key examples for the canonical one-stage chat subset. Real local disable/reload verified; hard gates remain server-side. | No operational enable was attempted or granted. API-key creation/revocation, safe provider connection metadata and listing endpoints do not exist in the frozen HTTP layer. No dummy controls or provider-key form. Alias/API examples are unit/contract-backed, not live inference evidence. |
| Runs/activity | Canonical synthetic sample preview and explicitly costed run action; exact run/output/trace reads; persisted SSE event timeline/usage subtotal; stop only in active states, no automatic retry, conservative uncertain-submission block. Fixture events/output tested. | No real run executed. No tenant-wide route/date activity query, attempt-read endpoint, workspace usage aggregation or historical replay scheduler; loaded-event subtotal is explicitly not total billing. Lost-submit lookup needs integration. |

The app performs no direct-provider browser request, embeds no secrets and stores
no sample/output/key payloads in localStorage/sessionStorage. Existing planning
session storage contains only opaque request hashes/idempotency IDs. Typed imports
are server-owned/tenant-scoped; trace content is rendered as text, never HTML.
New drafts do not modify an existing alias or carry old quality/activation status.
Server admission must enforce current workspace hard restrictions on every call.

## Catalog coverage and tool/access status

Reused the existing September 6 public snapshot: **8 artifact releases, 17 source
captures, 32 claims (5 capability claims), 1 endpoint declaration, 0 verified
callable target configurations**. No padding entries, rankings, new benchmark
measurements or synthetic facts promoted to real entries. Retained observations
and expired fields remain dated/stale; reading them is not a live refresh.

Current inventory discovery confirmed Bright Data search/extraction and Exa search
tools exist. They were not called: no approved billable runtime search credentials
or cap was supplied. No Codex connector was represented as an app adapter. Existing
protected official metadata/parsing paths were preserved; no new public metadata,
publisher API or inference request was made in this lane. No private workflow text
was sent to a public search service. No credential discovery, account creation,
credit assumption, purchase, model download, cloud provisioning or deployment.
Git/local shell, package tools and Playwright were the actual development tools.
Drive/hosting/database connectors were not re-tested or newly required.

## Executed checks

From this worktree's `router/`, unless noted:

| Command/check | Actual result |
|---|---|
| `UV_CACHE_DIR=.local/cache-lane8 uv sync --frozen --python /opt/homebrew/opt/python@3.12/bin/python3.12`; `npm ci --ignore-scripts` | Isolated dependencies installed; manifests/lockfiles unchanged. |
| Baseline `UV_CACHE_DIR=.local/cache-lane8 make check` | **296 passed**, lint/types/build/generation drift passed. |
| `node web/tests/unit.cjs` (also executed by pytest) | **14 assertions/groups passed**: exact refs, immutable diff, malformed editor data, typed inputs, literal prompts, redaction/consent, import limits, tenant/tool grant rejection, source URL safety, unknown costs and environment-only API examples. |
| `uv run pytest tests/studio tests/research -q --basetemp=.local/pytest-lane8-final` | **95 passed**. New TS-generated import and executable policy payloads validate through canonical Python contracts. New research review tests cover relevant freshness, absent subjects, immutable snapshots, duplicates/conflicts and recapture versus measurement. |
| Final `UV_CACHE_DIR=.local/cache-lane8 make check` | **305 passed**, 2 upstream warnings; Ruff lint/format, mypy (47 source files), ESLint, TypeScript, Vite build and canonical OpenAPI/generated-client/fixture drift all passed. No generated changes. |
| `playwright_cli.sh --session lane8 run-code --filename web/tests/browser_live.js` | **PASS**, real local API/worker/SQLite: plan rename/version, draft save/reload, disable, sample import/get, honest runtime 503, retained public catalog/search, old policy pin unchanged, 390px layout without horizontal overflow; 4 screenshots. No JS exceptions in successful run. |
| `playwright_cli.sh --session lane8 run-code --filename web/tests/browser_contract_fixtures.js` | **PASS**, explicit transport fixtures only: one comparison submission, completed and failed cells, safe untrusted output text, read-only refresh (no second submit), SSE status/usage, final output; 2 screenshots. Fixture interception removed afterward. |
| `git diff --check`, staged path audit, provider/private-key pattern scan | Passed; no matching real-key/private-key patterns; owned paths only. |
| `npm audit --json` | Two high-severity **development** findings (`js-yaml` / `@redocly/openapi-core`, GHSA-2883-xcg3-v3hh), integration lockfile update requested. No audit fix outside ownership. |
| `npm audit --omit=dev --json` | Zero production-dependency advisories returned in this check; not a broader security certification. |

The two Python warnings are existing Starlette/httpx and AnyIO deprecations.
Browser script iterations initially had label-matching/URL-global and sequencing
errors; final corrected scripts passed. Browser testing also found and fixed a
real small-screen overflow. Expected 503 network diagnostics are not a fake
success; fixture pass console check had no errors/warnings. Screenshots were
visually inspected (routes, public evidence, mobile and comparison).

## Isolated local review environment

Own API **8028**, UI **5198**, DB `router/.local/lane8.db`, UV cache
`.local/cache-lane8`, own venv/node_modules/Playwright session `lane8`. No shared
cloud DB or another lane's dev resource was used. Existing application services
on other ports were not changed. The isolated UI/API/worker remain running for
review; all runtime execution ports are uninstalled in this base.

```sh
ROUTER_DATABASE_URL=sqlite:///.local/lane8.db uv run python -m buildbox_router.storage
ROUTER_DATABASE_URL=sqlite:///.local/lane8.db ROUTER_WEB_ORIGIN=http://127.0.0.1:5198 uv run uvicorn buildbox_router.api:create_app --factory --host 127.0.0.1 --port 8028 --no-access-log
ROUTER_DATABASE_URL=sqlite:///.local/lane8.db uv run python -m buildbox_router.worker
ROUTER_WEB_PORT=5198 ROUTER_API_ORIGIN=http://127.0.0.1:8028 npm run dev --workspace web
```

Last passing real test: plan `0df89aa4e8f9483f94d4dddb16cbcb10` version 2;
disabled policy `studio-ec61718a-ab33-489c-8784-779d9f10b56c@1`;
sample `5e532f96-286f-4f49-9d20-9d8fe7582d9f` (one-day retention).
Public catalog review plan: `e4e61e8178114fcbae01b0446d759ec8` version 1.
These are synthetic/local test records, not customer data or operational approval.

Saved, ignored screenshots in `router/output/playwright/`:

- `lane8-real-routes-blocked.png` — persisted disabled draft and preview, run blocked.
- `lane8-real-comparison-blocked.png` — actual missing-runtime response.
- `lane8-public-evidence.png` — retained identity/license/access evidence and stale/unknown labels.
- `lane8-mobile.png` — narrow-screen studio without horizontal overflow.
- `lane8-CONTRACT-FIXTURE-comparison.png` — explicit fixture output versus failed cell.
- `lane8-CONTRACT-FIXTURE-activity.png` — explicit fixture status/usage and persisted-output rendering.

## Integration next steps — not performed

Read [exact shared change requests](../change-requests/lane-8/01-studio-integration.md)
and Lane 7's handoff. Shared prerequisites include authoritative edit/pin fields,
complete execution bindings, safe catalog/configuration/connection reads, bounded
independent refresh, key-product endpoints, attempt/activity/usage listings,
comparison admission/orchestration/metrics and split/consent/rubric provenance.
Runtime Lane 7 supplies ports but does not compose them or provide a completed
ComparisonPort; merely merging both lanes will not make all these screens live.

Integration owner must review and compose canonical ports, add approved shared
contracts/migrations where needed, regenerate clients, and run end-to-end tests.
Before any target smoke test, obtain one grouped operational approval for exact
artifact/revision/endpoint, independent server credential reference, data class,
privacy/retention, license/capabilities, calls/tokens/deadline and total spend.
Do not substitute synthetic admissions or copied Codex credentials. No merge,
push, publish, deploy, live inference or model-quality claim was made here.
