# Stakeholder demo handoff — September 13, 2026

## Baseline and scope

Branch: `codex/router-v2-integration`. Base:
`1593d043a27847612d861b5d6dc482dc677fa936`. Git ancestry confirms it already contains
`7213ad7e236244c6b79726b71ef40350cf4c9fb7`; no additional branch merge was necessary.
The final local commit is the commit containing this handoff (`git rev-parse HEAD`).
Other worktrees, prior company research and Founding Customer Radar were untouched.

## Changes

- Added a presentation component using canonical studio/gateway APIs and generated
  contracts. Existing full studio remains available; no alternate selection or
  direct-provider path was introduced.
- Added read-only typed demo metadata, visible only in the explicit offline test
  composition for its authorized tenant. Three deterministic fixture scenarios
  and one controlled pre-response failure seed real planning/policy records.
- Added safe one-command launcher with fresh private DB, fixed test authentication,
  isolated loopback ports, built UI, owned-process cleanup and credential-free child
  environment. Existing local services/data are not stopped or overwritten.
- Fixed completed SSE output retention: successful streams now persist the terminal
  completion when the pre-existing retention policy permits it. Default retention
  remains zero; incomplete streams are not stored as successful completions.
- Added six backend regression cases and actual browser acceptance/media. Human
  explanations derive from selector checks, catalog price order or explicit pins.

## Executed verification

- Baseline backend suite: **414 passed**.
- Final `make check`: **420 passed**, including the six new demo cases; Ruff lint
  and formatting, mypy (66 source files), ESLint, TypeScript, generated OpenAPI/client
  drift checks and production build passed. Two upstream test deprecation warnings.
- Separate `uv run pytest tests/gateway -q`: **115 passed**, two warnings.
- `node web/tests/unit.cjs`: **14 passed**.
- `uv run python -m tests.gateway.client_smoke`: **9 passed** (Python 4, TypeScript 4,
  cURL 1); synthetic transport only, eight accounted attempts and two tool round trips.
- Native PostgreSQL 17: `tests.gateway.pg_smoke` passed on fresh
  `buildbox_demo_20260913_clean`; `scripts/check_upgrade_postgres.py` passed on fresh
  `buildbox_demo_20260913_upgrade` (v2→v4, preservation, CAS/concurrency). Both use
  the existing isolated loopback cluster on 55440, not a managed database.
- Browser: `web/tests/stakeholder_demo.js` exercises three scenarios, two comparison
  cells, ten recorded attempts, two fallback attempts, original tool-call ID,
  schema-validated output, saved-stream reload and 390px layout. No live inference.
- Existing `web/tests/browser_upgrade.js`: **PASS** on a separate fresh test factory
  (8033/5203): public-packet workflow, four comparison cells/two samples, two expected
  semantic failures kept visible, six attempts, edited v2, stale admission denied,
  enabled v1 preserved, reload, alias creation and application-key issue/hide/revoke.

Screenshots/recording and the exact sequence are in `docs/STAKEHOLDER_DEMO.md`.
The final clean-start browser run passed again after the UI changes; console:
zero errors/warnings. Eight current screenshots were captured. The 10.72-second
unnarrated recording is the automated end-to-end flow, not a five-minute talk.
`git diff --check` passed; a targeted built-asset scan found no provider-key/private-key
patterns or public test password. This is a bounded check, not a secret-scanning guarantee.
Ordinary tests require no live credentials; no assertions or safety blockers were
removed to obtain a demo success. Initial harness authentication/setup mistakes
were corrected rather than bypassing the API's authentication or schema restrictions.

## Important boundaries

Small/medium labels are synthetic configurations, not real verified model releases.
Scenario B deliberately demonstrates a user pin, not automatic discovery of greater
intelligence. The strict-JSON step is separate from the tool-history call because
the current documented API subset rejects combining those modes. Every call is
accounted. The shipping lookup is an explicitly approved, simulated read-only
client tool; there is no live web search.

Fallback uses two configurations of the same loopback simulator. The first 503
leaves unknown cost visible; this is not an independent-provider uptime test.
Completed outputs are retained one hour in this synthetic composition. The shared
fixture responder is for a single-presenter demo, not concurrent load measurement.
The automated recording has no narration; the guide supplies the stakeholder story.

No live model quality, live inference, second-provider availability, external tools,
production reliability or deployment was validated. No push or publication occurred.
Remaining external prerequisites: authorized eligible targets, secure provider
credential references, explicit budgets/retention/privacy decisions, optional web
tool authorization and a protected full-stack hosting target. Never deploy the test
factory/public test identity. Production activation remains subject to security and
operational acceptance; this work declares only local sandbox-demo readiness.
