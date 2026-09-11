# Prompt 09 — integrated local sandbox router

September 10, 2026. Status: **local sandbox software integrated and verified;
live-provider and protected-preview acceptance incomplete**. Not production-ready.

## Verified Git foundation and preserved work

- Worktree: `/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-V2-Integration`.
- Branch: `codex/router-v2-integration`; no remote, push, deploy or other-project edits.
- Exact Prompt 6 base: `48ba6e2b2dc7d7d509cc68e2314c89dd5c54fec0`.
- Runtime lane tip: `027b950835eea9007dc8e4561b030eaea1772590`.
- Studio lane tip: `fe996d846499581a88c01e0f8c67f87a2285eb92`.
- Runtime merge `da7bb35` passed 346 tests before studio merge `51ee735` passed
  355. The initial base passed 296. Actual diffs and handoffs 07/08 were inspected.
- Discovered later central work was preserved, not overwritten: integration tip
  `7213ad7e236244c6b79726b71ef40350cf4c9fb7`, including implementation `57b6cf4`.
  Merge `eebbfd08cc8e10cb6dd594fee4f9b2afcae5d30d` passed 399 tests.
- Final implementation commit: `b19ede3d95c789a5cb4920069c890917f4a0c4d0`.
  This handoff is a subsequent documentation-only commit; `git rev-parse HEAD`
  identifies the final checkout. The other seven worktrees remain unchanged.

## Actual gaps repaired centrally

The merged baseline already had valuable streaming/tool schemas, guarded adapters,
durable worker/queue/accounting, keys and studio views. Those implementations were
preserved. The new integration repaired these actual omissions:

- Default API/worker runtime composition still received the legacy fixture
  selector while planning used the evidence-gated selector. New product composition
  uses `DeterministicSelector` across planning, drafts, comparison/runner and API.
- Arbitrary simple text tasks could dead-end on interpretation and descriptive
  answers. Added explicit one-model template proposals and targeted answer
  resolution, without pretending this is general model-assisted graph interpretation.
- Planning had no path to the operator's exact runtime snapshot. Added canonical
  artifact/configuration eligibility records and tenant-scoped snapshot binding;
  mandatory missing/stale evidence still blocks. Public discovery stays separate.
- Added bounded natural-language and structured edit proposals, source-version
  diffs, prompt ancestry, preserved pins/exclusions, output schemas and history.
  Every material saved change is a new provisional draft requiring fresh admission.
- Added deterministic schema/reviewed exact-match comparison checks, inert tool
  schemas and tuning/holdout import labels. Actual failed answers remain visible.
- Added persisted intermediate outputs, bounded real aggregated attempt usage,
  per-attempt upstream/pre-dispatch timing and comparison completion timing.
  All actual fallback attempts are included in final run references.
- Source inputs are separate from the pinned system template; fixed public packet
  tools are tenant-bound, read-only, bounded and expiry/revocation checked.
  Local-only imports also constrain fallbacks. Current registry authority is
  reloaded, rather than treating startup approvals as indefinitely valid.
- Added a bounded immutable-content selection cache, never caching grants/budgets
  or extending evidence expiry. Normal inference does not launch public research.
- Added runnable Python/TypeScript examples and a real-local-HTTP client harness;
  no second direct-provider UI path or custom SDK.

Shared changes live under `router/backend/buildbox_router/` contracts, composition,
planning, selection, gateway, policy/comparison/storage and runtime modules. UI
changes live under `router/web/src/`; generated clients/OpenAPI remain centralized.
Tests/acceptance factories are under `router/tests/gateway/` and `router/web/tests/`.
Use `git show --stat b19ede3` for the exact 47-file implementation/documentation diff.

## Contracts, migrations and checks

Canonical additions are backward-compatible JSON fields; no competing API schemas
or new database were introduced. The existing centrally merged v4 migration remains
the database revision. Legacy policy digest defaults are preserved and tested.
OpenAPI, TypeScript and the synthetic contract fixture were regenerated and checked.
The root dependency lockfile was reconciled; no application stack replacement.

Final executed checks on this implementation:

| Command/check | Result |
|---|---|
| `UV_CACHE_DIR=.local/cache-integration9 make check` | PASS: 414 backend tests; Ruff/format, mypy (65 source files), ESLint, TypeScript, Vite build, generated-schema/fixture drift. Two upstream deprecation warnings. |
| `node web/tests/unit.cjs` | PASS: 14 studio checks. |
| `uv run python -m tests.gateway.client_smoke` | PASS: Python 4, TypeScript 4, cURL 1; 8 synthetic upstream attempts; 2 tool-result ID round trips; 0 external requests. |
| `tests.gateway.pg_smoke` on `buildbox9_clean_utf8` | PASS: clean isolated PostgreSQL v4 + HTTP/worker/checkpoint/ownership/accounting. |
| `scripts/check_upgrade_postgres.py` on `buildbox9_upgrade_utf8` | PASS: v2→v4, rerun, preserved legacy, immutable records, tenant/CAS/budget checks. |
| Playwright `web/tests/browser_upgrade.js` | PASS on actual UI/API/worker/HTTP synthetic upstream: public packet pipeline, 4 comparison outputs, stale admission denial, old pin preservation, reload, key issue/hide/revoke, mobile layout. |
| `npm audit --omit=optional`; `git diff --check` | PASS: zero audit findings; no whitespace errors. |
| Built frontend bounded secret-pattern scan | No provider/private-key or synthetic Basic password patterns found; not a complete independent audit. |
| Real two-target inference, runtime web search, managed secrets/DB, protected preview | NOT RUN: no recorded access/operational approval available. |

The original shared tests were not weakened. New tests cover product selector
wiring, current eligibility, modality/tool distinction, current-registry and packet
revocation, cache invalidation, provisional edits, typed checks and scoped outputs.
The earlier failure/security tests remain passing. See
[actual evaluation report](../ROUTER_V2_EVALUATION.md) for failures encountered,
dataset/configuration versions, measured quantities and limitations.

## Operational boundary and reproducible handoff

See [reviewer guide](../REVIEWER_GUIDE.md) for exact local API/worker/UI commands,
the demo script and screenshot/video paths. Normal local product is at
`http://127.0.0.1:5200`; explicit synthetic acceptance at `http://127.0.0.1:5201`.
Neither is a shareable preview. Native PostgreSQL uses an isolated temporary
cluster on port 55440, not Neon/Supabase or production. Generated browser artifacts
remain local/Git-ignored; the final recording is
`router/output/playwright/09-integrated-final.webm`.

LIVE INFERENCE = NOT VERIFIED. LIVE SECOND UPSTREAM = NOT VERIFIED. The real
compatible HTTP transport was exercised only against a synthetic server;
OpenRouter and native-local transports passed offline fixtures. No connector
credentials were copied into the app. No web tool was authorized: fixed retained
public metadata is explicitly labeled and does not constitute company research.
Application-key onboarding worked against the local authenticated API; upstream
credential provisioning into an approved managed store could not be verified.

The remaining operational request is one coordinated approval: exact source-backed
eligible configurations/endpoints, server secret-store references, data/retention
policy and total bounded spend; optionally a selected protected preview/backend/
worker/database target. Do not paste secrets in chat or create fake admissions.
No hosting limits were changed or paid resource purchased. There is no deployed URL.

Remaining implementation limits are explicit, not attributed solely to access:
general NL multi-tool DAG interpretation needs a configured interpreter or reviewed
manual graph; current comparisons require sandbox-admitted policies before testing;
human-pause resumption, free-form semantic rubric execution and full-request/
first-content timing for nonstream workflows are not implemented. Raw input runs
are conservatively tenant-private unless bound to an imported sample. Public
catalog updates never automatically migrate an enabled alias. These boundaries
prevent calling this a completed live/production router.
