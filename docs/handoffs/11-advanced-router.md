# Milestone 11 — advanced workload intelligence

September 13, 2026. Branch: `codex/router-v2-integration`.
Verified starting commit: `7bff0878d68921a11b6b35e238f8b6d1d66eddce`.
This handoff accompanies the implementation commit; resolve its full hash with
`git log -1 --format=%H -- docs/handoffs/11-advanced-router.md`.
Only this integration worktree was changed; no branch merge, push or deployment.

## Outcome and scope

**PARTIAL against the entire 35-phase specification; working bounded intelligence
sandbox implemented and original demo preserved.** It now makes task-specific
model/deployment/strategy decisions, compiles them into the existing runtime, and
explains the evidence, alternatives and uncertainty. This is materially more than
an API proxy. It is not a general-purpose autonomous orchestration platform or a
validated model-quality optimizer.

Implemented: normalized dated capabilities/performance records, workload overrides,
hard gates, normalized utility, Pareto/confidence, five bounded plan strategies,
task-specific stage selection, exact decision/catalog/policy history, what-if/shadow,
catalog diff, modular output validators, validation escalation, deployment circuits,
decision-level metrics/API/UI, and D–J deterministic scenarios.

Read `ADVANCED_ROUTER_AUDIT.md`, `OPEN_WEIGHT_ROUTER_ARCHITECTURE.md` and
`ADVANCED_ROUTER_EVALUATION.md` for the inspected baseline, implementation and evidence.

## Actual checks executed

| Check | Final result |
|---|---|
| `uv run pytest -q` | **466 passed**, two pre-existing deprecation warnings |
| `uv run pytest tests/gateway -q` | **161 passed**; subset of the 466, not additional coverage count |
| `uv run pytest tests/gateway/test_advanced_router.py -q` | **46 passed**; subset of the above |
| `node web/tests/unit.cjs` | **14 passed** |
| `make lint typecheck build check-generated` | PASS: Ruff lint/format (119 files), ESLint, mypy (74 sources), TypeScript, production Vite build, OpenAPI/TS and canonical fixture drift |
| `uv run python -m tests.gateway.client_smoke` | **9 passed**: four Python, four TypeScript, one cURL; eight synthetic HTTP attempts, two tool-ID round trips |
| `uv run python -m tests.gateway.evaluate_advanced --output output/advanced-evaluation.json` | **9 A/B decisions, 8 successful synthetic workflows, 10 attempts, 1 expected tool-authority block** |
| `web/tests/advanced_router.js` via Playwright CLI | PASS D–J, six distinct scenario executions, repeated H escalation, decision reload, what-if, stale-admission reset, mobile width |
| `web/tests/stakeholder_demo.js` via Playwright CLI | PASS A–C, actual SSE/persisted replay, two comparison cells, tool/JSON round trip, two fallback attempts, mobile width |
| `web/tests/browser_upgrade.js` via Playwright CLI | PASS retained public-packet workflow, two samples/four comparison cells, two expected exact-match failures, six attempts, edits, old versions, stale admission rejection, key create/hide/revoke, reload |
| Native PostgreSQL clean + upgrade | PASS clean migration/rerun and v2→v5 upgrade, preserved records, immutable policies/aliases, tenant boundary, concurrent reservations |
| `git diff --check` | PASS |

Ordinary tests remain offline except explicit exact-port loopback HTTP fixtures.
No assertion was dropped to obtain a pass. Migration expectations moved from 4 to 5;
the legacy policy test now reconstructs the real old shape and additionally asserts
its fixed pre-upgrade digest. Generated fixtures were regenerated, not hand-edited.

Intermediate failures fixed: one stale migration expectation, canonical fixture
drift, old-shape digest reconstruction, typed objective-key access and the browser
test runtime's unavailable `URL` global. Initial PostgreSQL checks encountered the
existing SQL_ASCII cluster's client encoding; `PGCLIENTENCODING=UTF8` resolved it.
The browser's intentional stale-admission 403 is an expected negative check, not a
hidden network failure. No unexpected page exceptions or horizontal mobile overflow
were found in the completed browser scenarios.

## Local start and D–J

From this checkout's `router/`:

```sh
BUILDBOX_DEMO_API_PORT=8034 BUILDBOX_DEMO_WEB_PORT=5204 make demo
```

Open `http://127.0.0.1:5204/?intelligence=1`.
Local test identity: `fixture` / `synthetic-test-password` (not production credentials).
The final verification left this local demo running. If it is already running, open
the URL rather than starting a duplicate. Ctrl-C stops only its owned services;
rerunning creates fresh isolated storage without deleting prior audit data.

1. Select D, E or F. Inspect **Understood requirements** and **Candidate tradeoffs &
   exclusions** for context, privacy or hard cost gates.
2. Select G. Inspect small → medium → small per-stage choices and dependency order.
3. For D–I, review **Executable prompts and typed input bindings**, check the explicit
   sandbox approval, and click **Enable sandbox & run**. Inspect persisted outputs
   and individual attempts. These are stage checkpoints, not pretend token streams.
4. Select H and run: inspect the failed literal validator and accounted escalation.
   It is repeatable. Select I to inspect the unhealthy deployment exclusion and
   equivalent deployment selection.
5. Select J, then **Prioritize quality**: small changes to medium without inference.
   **Prepare executable draft** shows that the old admission cannot carry over.
   **Evaluate shadow policy** creates a decision-only comparison.
6. Use **Original demo A–C** for streaming/tools/JSON/comparison; **Full workflow
   studio** for prompt edits, history, imports, aliases and application keys.

Browser automation sources are committed. Generated local evidence is under
`router/output/playwright/` and `router/output/advanced-evaluation.json`; these are
intentionally ignored generated artifacts. No new polished recording was produced.

## Migration notes

Forward-only revision 5 adds one target-scoped mutable health table. Existing
append-only policy/catalog/output references are not rewritten. Native checks used
only isolated databases `buildbox_advanced_clean_20260913` and
`buildbox_advanced_upgrade_20260913` on the existing loopback PostgreSQL port 55440.
No managed database or production data was touched.

Commands used from `router/` after creating these empty databases:

```sh
PGCLIENTENCODING=UTF8 ROUTER_DATABASE_URL=postgresql+psycopg://aradhyamishra@127.0.0.1:55440/buildbox_advanced_clean_20260913 uv run python scripts/check_postgres.py
PGCLIENTENCODING=UTF8 ROUTER_DATABASE_URL=postgresql+psycopg://aradhyamishra@127.0.0.1:55440/buildbox_advanced_upgrade_20260913 uv run python scripts/check_upgrade_postgres.py
```

These check scripts deliberately refuse a nonempty database; do not rerun them on
application data. SQLite migration and circuit concurrency were also exercised in
the normal tests. Native PostgreSQL checks validate migration and shared budget
concurrency, not every health-policy race under production load.

## Remaining implementation limits

- Strategy selection is transparent bounded templates/rules, not global DAG utility
  optimization. Generate/verify has no conditional repair. A verifier may be the
  same configuration; independence is not claimed.
- General natural-language ambiguity/negation needs explicit overrides. Preferred
  cost and sensitivity annotations do not automatically rewrite objective weights.
- Automatic named-tool and multimodal execution is blocked. Existing reviewed
  read-only tool workflows still work; arbitrary code/unit-test execution is absent.
  Restricted data is blocked because the runtime has no corresponding grant class.
- Performance facts require reviewed snapshot ingestion. No automatic quality
  learning or benchmark-import UI was added, and no real quality dataset is present.
- Circuits affect availability; they are not time-decayed health estimation. Some
  provider errors remain coarse; no arbitrary context/tool-error repair strategy.
- Router aggregates are bounded and lack dedicated aggregate tool/schema-rate views.
  Full outputs/comparison metrics remain in the existing studio.
- Strict validators require nonstream completion. Advanced UI displays persisted
  stage checkpoints; token SSE remains available through compatible stage aliases
  and the original demo.

Before production: calibrate routing/strategy confidence with real held-out outcomes,
add reviewed conditional repair if evidence warrants it, enforce operational
retention/quotas for growing decision snapshots, and load-test cached stage checks
and circuit recovery. Keep current privacy/grant/freshness checks authoritative.

## External and evidence boundaries

No live provider credentials/eligible targets or inference budgets were supplied.
No vendor inference, new public research, external runtime web tools, cloud
provisioning or deployment was attempted. The compatible HTTP transport, runtime,
validation, persistence and accounting executed for real; advanced model facts,
prices, task scores, health setup and responses are explicitly synthetic. A Codex
connector was not installed as a runtime adapter. No live quality validation,
production reliability or production-readiness claim is made.

Best next milestone: a small reviewed outcome-linked holdout suite evaluated against
two approved real open-weight deployments and a pinned single-model baseline, with
explicit authorized budgets. Use those results to calibrate strategy selection and
confidence rather than expanding the fixture catalog.
