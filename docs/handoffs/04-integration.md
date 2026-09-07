# 04 — Integration handoff

Status: **usable local planning alpha; not a verified production router or a source
of verified non-synthetic target configurations.** Both runtime control-plane paths
were exercised through the real authenticated local app/API/worker. No paid
provider calls, model downloads, purchases, public deployment, production routing,
active policies, or automatic migration occurred. Evaluation remains `not_run`.

## Exact Git state

- Integration branch: `codex/router-integration`.
- Integration worktree: `/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-Integration`.
- Tested implementation: **`080af77c841cef17a3e8b44950c5dd0c48122d00`**.
- Foundation: `b36437fc91b717b3978f977ec3cdf084c8206a5b`.
- Intelligence tip: `5e1e3c2ef8a063c5d3c0374f455b463ed0291ff9`;
  implementation `71e8227195ef3a2fa0f7e1c01f4591482f5df5d6`.
- Research tip: `7c8ca2b0b80b4e4c3254c0b9b2f49be54a96b7d1`;
  implementation `a212267ce53d6eb59e80ecf39578960669434c46`.
- Verified both lane merge bases are the intended foundation. Inspected actual
  diffs and handoffs, then merged intelligence (`06eda2c`) and research (`fc58e3c`)
  separately with checks between merges. No merge conflicts, protected-main
  changes, remote writes, or parallel-worktree edits.
- Foundation's untracked research folders/files remain intact; both lane
  worktrees remain clean. This handoff/evidence is a following documentation-only
  commit, so its own commit hash is deliberately not self-referential.

## Delivered behavior

Natural-language intake → validated interpretation or targeted questions →
explicit edits/answer records → immutable new version → pinned public/synthetic
catalog and research ledger → deterministic filtering/selection → saved result →
evidence inspection → inactive, secret-free policy export.

- React uses generated API types and the existing visual system. Three examples,
  processing controls before calls, editable graph JSON, accessible stage/dependency
  list, bounded loops, job progress/cancellation, reload URLs, answer preservation,
  missing facts, exclusions, alternatives, evidence, version/staleness and draft
  download are wired to real API data. No fake progress or evaluation metrics.
- Extraction/support fixture flows export inactive mappings. Company research
  shows a bounded graph but blocks assignment because exact tool-call evidence is
  missing. Images/self-host/structured-output/model-tool-call requirements do not
  silently pass. Code-only text steps require no model or research call.
- Changes create new versions. Earlier recommendations remain immutable and
  visibly stale; old exports fail. Unsaved form changes also disable export.
- Tenant-scoped reads/writes, operator-provisioned PBKDF2/HTTP Basic identities,
  owner-scoped idempotency, durable progress, attempt-token leases, bounded
  recovery, transactional result writes, cancellation and conservative budget
  holds are implemented. Legacy fixture endpoints cannot access planning records
  to bypass exact-version checks, and are unavailable in shared/live mode.
- Recovery after any paid reservation requires reconciliation, including a crash
  after known accounting but before result persistence. Cancellation prevents
  result commit; it does not promise to undo already-dispatched provider work.
- Rich evidence types were promoted centrally; the lane module re-exports them.
  No duplicate canonical schema/client or lockfile change was required. Revision 2
  is explicit only. Retained public source files are byte-identical to lane captures
  and included in the built Python wheel, not read from test directories at runtime.

## Actual verification results — September 6, 2026

| Check | Result |
|---|---|
| Foundation `make check` | 36 tests; lint/types/build/generated checks passed |
| After intelligence merge | 134 tests; full checks passed |
| After research merge | 217 tests; full checks passed |
| Final `make check` | **250 tests passed**; Ruff lint/format, mypy (39 sources), ESLint, TypeScript, Vite build and generated drift passed |
| Python distribution | `uv build` passed; wheel contains both public snapshot JSON files |
| Isolated SQLite | Explicit clean revision-2 migration and rerun; durable API/worker/browser flows passed |
| Isolated PostgreSQL 17.11 | UTF-8 database: clean migration/rerun, real API/worker/policy, version staleness, immutability and concurrent approval cap passed |
| Browser suite | Extraction/export, corrected answer/reload/staleness, support/tool, bounded company research, image, self-host, strict egress, no-model, retained missing-configuration evidence, real public research passed |
| Authenticated failure browser | Injected provider timeout at provider boundary, real persisted failure, reload, cancellation and cross-tenant read/cancel/export denial passed |
| Browser diagnostics | Final checked sessions reported zero console errors/warnings; expected negative HTTP responses are intentional assertions, not substituted successes |

Two upstream FastAPI/Starlette test-client deprecation warnings remain. Docker's
existing containerd image-store I/O error remains untouched; native PostgreSQL
removed the database verification blocker. An early API start before migration
correctly failed; explicit migration followed by restart succeeded. Headed-browser
screenshots timed out; headless screenshots succeeded and were visually inspected.
Initial test timing waited on a textarea before reload hydration; the check now
waits on the actual persisted version/status, then asserts the restored answer.

These are integration checks, not statistically representative evaluations or
model-quality measurements. No mandatory lane tests were removed or weakened.

## Runtime integrations: verified versus unverified

**Verified through authenticated `ROUTER_MODE=live`, not a development connector:**

- Plan `f3073d61e0e549518d51fd16dbc16392`, version 1, tenant `alice`, isolated
  `.local/live-alpha.db`. Browser/API on loopback 5186/8016 with a real worker.
- Synthetic request: “Use an LLM to classify input text as positive or negative
  sentiment and return a label.” Actual output contains a validated `classification`
  LLM node and preserved constraints. No target workflow was executed.
- Ollama 0.32.5; pre-existing cached `qwen2.5:0.5b`, digest
  `a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67`.
  Reported 779 prompt / 63 output tokens. These are recorded usage, not quality.
- Runtime worker then fetched `https://huggingface.co/api/models/Qwen/Qwen3-8B`,
  observed `2026-09-06T23:44:36.267525Z`, retaining non-synthetic source/evidence.
- Permission record is the persisted plan's explicit `local_model` and
  `public_research=true` processing choices under the integration request, with
  `max_planning_usd=0`; isolated loopback inference, cloud disabled, no credential
  use and no model download. Each local call is bounded to 1,400 output tokens;
  public research uses one approved fixed metadata request. Paid-provider spend: $0.
- The result is **blocked**, correctly: control-plane inference plus publisher
  metadata is not evidence for a runnable target configuration.

Earlier local-model attempts returned invalid bindings/tool fields/empty outputs
and remain failed jobs; an early schema-valid interpretation also failed the smoke
test's expected model-stage assertion. Schema guidance was corrected without
relaxing graph validation, and explicit model-stage requests are enforced. The
successful final check does not establish general language-understanding quality.

**Implemented/offline-tested, not live-verified:** OpenRouter. No recorded hosted
provider/key permission or spend cap was supplied. No key was discovered/reused,
and no Codex credential was copied. Exact qualified endpoint allowlisting, required
parameter checks, no fallback, pricing/budget checks, denied data collection, ZDR,
and retained actual provider/model/usage metadata are implemented. Exact served
endpoint attestation is explicitly unknown when absent in the response. Separate
role configuration permits different authorized model/endpoint/key choices;
research currently needs no LLM. See official source links and detailed gates in
[INTEGRATION_RUN.md](../../router/INTEGRATION_RUN.md).

## Local commands and review instructions

Use [INTEGRATION_RUN.md](../../router/INTEGRATION_RUN.md) for complete fixture,
authenticated live, local-model and PostgreSQL commands. In the integration
worktree:

```sh
cd router
make check
uv build
```

The fixture UI is available at http://127.0.0.1:5184. Reloadable example:
`?plan=0214964036934ed2ae2057048fff3503&version=2`. Browser commands used:

```sh
playwright-cli --session router open http://127.0.0.1:5184
playwright-cli --session router snapshot
playwright-cli --session router run-code --filename scripts/browser_checks.js
playwright-cli --session router run-code --filename scripts/browser_local_runtime.js
playwright-cli --session router console warning
playwright-cli --session router requests
```

This host used `/Users/aradhyamishra/.codex/skills/playwright/scripts/playwright_cli.sh`
as the CLI wrapper. Live checks are opt-in, not part of offline CI. Failure/auth
checks use the explicitly test-only server and public synthetic test identities.
The installed CLI uses `requests` for its network inventory; the skill reference's
older `network` command is unavailable and was corrected after inspecting CLI help.

PostgreSQL was independently initialized under `/tmp/buildbox-router-pg.ckgqA6`,
bound to 127.0.0.1:55484; database `buildbox_check` was created UTF-8 from template0.
Executed:

```sh
ROUTER_DATABASE_URL=postgresql+psycopg://buildbox_test@127.0.0.1:55484/buildbox_check uv run python scripts/check_postgres.py
```

Review with `git show 080af77` and
`git diff b36437fc91b717b3978f977ec3cdf084c8206a5b..080af77 -- router docs`.
Inspect the central planning contracts/storage/runtime boundaries before UI details.
Artifacts are local/ignored: `router/output/playwright/planning-alpha.png`,
`authenticated-provider-failure.png`, downloaded inactive policy JSON, and the
three isolated SQLite databases. Test-only auth/live servers and PostgreSQL are
stopped after verification; retained databases are not deleted. Existing services
on 8000/5173 were not changed.

## Remaining release gates / integration requests

1. No non-synthetic target has complete verified download/license/context/hardware,
   endpoint capability, prompt/harness and workload-evaluation evidence. Preserve
   blocked results until this evidence exists; do not promote the planning model.
2. Exact tool-call evidence is missing for the bounded company-research example.
   The small local interpreter supports acyclic code/model/approval sketches, not
   general tools/loops. Graph edits preserve canonical checks; empty data bindings
   are visible planning gaps, not executable wiring.
3. Hosted OpenRouter use needs genuine role/key/spend approval and a real smoke
   test. A config file or discovered key alone is not permission.
4. Shared/public deployment remains unauthorized. TLS, operational identity
   provisioning/recovery and deployment review are required before non-loopback use.
5. Evaluation metrics, production suitability, savings and model quality remain
   unrun/unclaimed until the next milestone.

## Shared files touched

`docs/TOOLS.md`, `docs/contracts.md`; router configuration/env example, API,
canonical Job contract, explicit migrations, storage, worker, promoted evidence
types/compatibility re-exports, generated OpenAPI/TypeScript, React entry/UI/styles
and Vite proxy configuration. New integration-owned planning/runtime/auth modules,
packaged public snapshots, tests and reproducible check/setup scripts are listed
in the implementation commit. Existing lockfiles, protected main, unrelated
internship research and the prior Radar workspace were not modified.
