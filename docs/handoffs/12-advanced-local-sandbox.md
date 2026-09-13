# Advanced Open-Weight Router Local Sandbox — completion

September 13, 2026. Branch `codex/router-v2-integration`.
Verified starting commit: `b3d19385c986cdb3b46d0b899259f9d9af409743`.
This handoff accompanies the local completion commit; resolve the exact hash with
`git log -1 --format=%H -- docs/handoffs/12-advanced-local-sandbox.md`.

## Scope and implementation

This milestone evaluates the **local sandbox**, not the broader production platform
specification. Existing workload routing, hard gates, task evidence, Pareto,
what-if, fallback, health, SSE, scoped keys and persistence are preserved.

- `routing_contracts.py` adds reviewed `ExecutionPlan`/`PlanStage` inputs. Eight
  bounded text nodes support arbitrary dependency order, independent branches and
  fan-in. All strategy templates compile through the same representation into the
  existing canonical workflow, prompts and typed bindings. Validation/recovery are
  explicit bounded post-generation control steps within each node; no second DAG
  runtime, autonomous planner or new authority was introduced.
- `planner.py` reserves original + fallback + repair calls, separately rounded
  cost envelopes and worst-case critical-path latency. Reserved `input` IDs,
  cycles, missing dependencies, duplicate IDs and impossible caps are rejected.
- `gateway/service.py` performs up to two requested repairs, within the existing
  three-total-attempt stage cap. Invalid output/checks are retained privately and
  supplied as untrusted data. Every repair re-enters preflight and authorization.
  Tool-bearing repair and streaming validated output remain blocked.
- `gateway/runner.py` retains dependency-wave execution and sequential checkpoint
  publication. All settled attempts now produce usage events, including failures,
  escalation and repair. Known-charge validation exhaustion is failed; interrupted
  authorization/unknown charges preserve conservative uncertainty.
- `gateway/outcomes.py` appends content-free terminal workflow observations. Studio
  APIs query owned outcomes and accept one immutable explicit rating per outcome.
  No outcomes or ratings influence ranking or become benchmark truth.
- Routing confidence is distinct from model-quality confidence in contracts,
  explanations and UI. A constraint-driven winner can be high confidence relative
  to the pinned synthetic catalog; model-quality confidence remains LOW.
- Scenario K shows invalid generation → deterministic verifier failure → one repair
  → passing verification. Original/final output, both attempts, reasons, usage and
  outcome feedback are inspectable. Original A–J scenarios are retained.

Canonical schemas/TypeScript/fixture are generated centrally. Default repair zero
is omitted from legacy admission-digest serialization; existing signed fixture
hash compatibility is tested. Edits preserve bounded repair configuration without
reusing approval. No dependencies, transport adapters, migrations or new databases
for the application were introduced. Outcomes reuse append-only sandbox records;
original outputs reuse authorized private TTL storage. Prior runs are not backfilled.

## Local demo

From this checkout's `router/`:

```sh
BUILDBOX_DEMO_API_PORT=8038 BUILDBOX_DEMO_WEB_PORT=5208 make demo
```

Open `http://127.0.0.1:5208/?intelligence=1`. Public test identity:
`fixture` / `synthetic-test-password` (not an upstream credential).

1. Choose **K · Generate → Verify → Repair**.
2. Inspect the selected configuration, separate confidence labels, validator,
   maximum repair count, two-call cap, and exact policy/prompt preview.
3. Review the synthetic input and check the explicit sandbox approval box.
4. Click **Enable sandbox & run**.
5. Inspect the incomplete original output, failed check, repair attempt and passing
   final check. Outcome history shows two attempts, one repair, no fallback and
   known versus unknown costs. Optional rating is explicit, not model ground truth.

Run again for a new bounded execution. Restart the demo command for a fresh
isolated database; previous audit data is not deleted. The URL is local, not shareable.

## Verification — PASS for the advanced local sandbox

| Executed check | Final result |
|---|---|
| `uv run pytest -q` | **485 passed**, two existing FastAPI/Starlette deprecation warnings |
| `uv run pytest tests/gateway -q` | **180 passed** (subset, not additional tests) |
| `uv run pytest tests/gateway/test_sandbox_completion.py -q` | **19 passed** (subset) |
| `node web/tests/unit.cjs` | **14 passed** |
| `make lint typecheck build check-generated` | PASS: Ruff lint/format (121 files), ESLint, mypy (75 sources), TypeScript, Vite production build, OpenAPI/TS and canonical fixture drift |
| `uv run python -m tests.gateway.client_smoke` | **9 passed**: Python 4, TypeScript 4, cURL 1; eight synthetic HTTP attempts; two tool-ID round trips; no external requests |
| `uv run python -m tests.gateway.evaluate_advanced --output output/advanced-completion-evaluation.json` | **9 policy comparisons, 8 synthetic workflow executions, 1 expected unapproved-tool block**; no model-quality conclusion |
| Playwright `web/tests/advanced_router.js` | PASS D–K: seven distinct scenario runs plus repeated H; J what-if; immutable decision reload; K original output/failure/repair/success, two attempts, explicit rating; mobile layout |
| Playwright `web/tests/stakeholder_demo.js` | PASS A–C: actual SSE and saved replay, two comparison cells, JSON/tool-ID round trip and bounded fallback; no unexpected page errors |
| Playwright `web/tests/browser_upgrade.js` | PASS full studio: public-packet run, two samples/four comparison cells, two expected exact-match failures, six attempts, old version preservation, stale admission rejection, key issue/hide/revoke, reload |
| Native PostgreSQL clean + upgrade | PASS clean migration/rerun and v2→v5; preserved legacy records, immutable aliases/policies, tenant boundaries and concurrent budget caps |
| `git diff --check` | PASS |

Native checks used new empty UTF-8 databases `buildbox_final_clean_20260913` and
`buildbox_final_upgrade_20260913` on the already-running local PostgreSQL port 55440,
with `scripts/check_postgres.py` and `scripts/check_upgrade_postgres.py` respectively.
No managed or user application database was changed. Test artifacts remain under
ignored `router/output/`; no screenshot-polishing or recording work was added.

Intermediate failures were fixed, not waived: a missing test import, new generated
default fields, separate gateway/workflow retention wiring, per-attempt rounding,
repair latency envelopes, and an overly broad error reclassification that changed
post-dispatch key-revocation behavior. That conservative behavior was restored.
No existing tests were deleted or weakened; confidence assertions now explicitly
check the quality-confidence label and retain their threshold expectations.

## Evidence and external boundaries

Routing, typed planning, execution, validation, authorization, persistence and
accounting are actual software behavior. Model responses, catalog facts, benchmark
values and injected health states are synthetic. Measured elapsed software time
does not establish live provider performance. Literal acceptance terms are a
deterministic fixture check, not semantic quality verification.

No live credentials, inference/search budget, eligible live target, external runtime
tool grant or deployment authorization was supplied or used. No paid calls, model
downloads, provisioning, public deployment, push or production merge occurred.
These are external/live-validation requirements, not blockers for this local
sandbox milestone. Production readiness and quality improvement are not claimed.

## Non-blocking future work

Outcome pagination/export and operational snapshot quotas; a richer reviewed DAG
editor; empirical calibration using approved real workloads. Graph bounds, blocked
unreviewed tools and nonstream strict validation are intentional safety boundaries,
not pending autonomous execution features.
