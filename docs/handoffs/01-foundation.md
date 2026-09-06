# Foundation handoff · September 6, 2026

**Parallel-ready: YES, for the two offline coding lanes.**
**Live/production-ready: NO. PostgreSQL runtime verification: BLOCKED.**

The implementation is complete for the explicit synthetic fixture path. Neither
lane was started; no branch/worktree for either lane was created. No remote push,
deployment, billable inference/search, customer workflow action or traffic change
was performed.

## Foundation identity

Branch: `codex/router-foundation`.
This previously uncommitted repository's initial commit is the foundation commit.
The exact immutable hash can be obtained with:

```sh
git rev-list --max-parents=0 codex/router-foundation
```

The final delivery message also records that exact hash. The foundation commit
contains this handoff and all implementation files; there is no hidden bootstrap
commit or dependency on an uncommitted sibling project.

## Delivered files

- `router/backend/buildbox_router/contracts.py`, `ports.py`: canonical v1 records,
  graph/reference validation, provenance/unknown semantics, and frozen interfaces.
- `intelligence/fixture.py`: exact-example interpretation/material clarification,
  hard filtering, synthetic ranking/comparison, stage assignments, safe policy
  compilation and an explicitly not-run evaluation adapter.
- `research/fixture.py`: reproducible synthetic catalog, separate model/config
  facts and auditable synthetic evidence. No real model claim imported.
- `api.py`, `composition.py`, `adapters.py`, `config.py`, `errors.py`: injected
  services, typed API errors, local fixture identity and fail-closed live/shared
  modes. No credential-dependent client is created on import.
- `storage.py`, `migrations/`, `worker.py`: durable owner-scoped records, immutable
  workflow versions, persisted jobs, CAS claim tokens, bounded stale leases and
  atomic recommendation/snapshot completion. Same backend package, one worker.
- `router/web/`: React/TypeScript UI using generated API types; save, poll,
  evidence inspection, inactive download and saved-job reload.
- `router/openapi.json`, `scripts/generate_contracts.py`,
  `scripts/check_generated.py`: reproducible generated contract artifacts and
  drift verification. No competing hand-maintained frontend schema.
- `router/tests/{intelligence,research,integration}/`: isolated lane and acceptance
  tests; temporary databases and denied outbound sockets.
- `router/pyproject.toml`, `uv.lock`, `package.json`, `package-lock.json`,
  `Makefile`, `.env.example`, `compose.yaml`, `README.md`: reproducible local setup.
- Root `AGENTS.md`, `.gitignore`, `README.md`, and `docs/`: safety, requirements,
  tools, ownership and handoff instructions. Existing research is untouched.

## Executed checks and results

All commands below ran from `router/` unless otherwise stated.

| Command / check | Actual result |
|---|---|
| `uv sync --python /opt/homebrew/opt/python@3.12/bin/python3.12` | Installed isolated backend environment and wrote lockfile |
| `npm install --ignore-scripts` | Installed UI/tooling dependencies; lockfile written |
| `make setup` followed by `make check` | Frozen Python sync and clean npm reinstall succeeded; all checks passed again |
| `make migrate` (including second execution) | Revision 1 created; rerun succeeded without data loss |
| `npm run generate` | OpenAPI and frontend TypeScript generated successfully |
| `make check` | Ruff lint/format, ESLint, mypy, TypeScript, pytest, Vite build and generated-drift checks all passed |
| `uv run pytest -q` | **36 passed**, including separate-process durable reload |
| `make test-intelligence` | **7 passed** independently |
| `make test-research` | **3 passed** independently |
| `npm audit` after updating Vite | **0 vulnerabilities** reported |
| Playwright CLI headed browser flow | Example → saved workflow/job → succeeded recommendation → evidence → JSON download passed |
| Saved job URL reload | Recommendation/workflow restored from persisted API data |
| Downloaded policy assertions | `draft`, inactive, no production writes, no execution connections; credential-key scan passed |
| Source credential-pattern scan | No provider-key/private-key/personal-email pattern matches in implementation/source docs |

The initial UI run found a favicon 404; an explicit empty favicon fixed it. An
initial build error from an unnecessary CSS import was removed and the build
rerun successfully. The dependency audit found an outdated Vite version; it was
updated to 7.3.6 before final checks. Pytest still emits **two upstream
Starlette/httpx/AnyIO deprecation warnings**; npm also emits an ESLint version-support
notice. No test failures are hidden, and the npm audit reports no vulnerabilities.

Acceptance coverage includes invalid DAGs/bindings/undeclared tools/unbounded
agents, distinct null/false/zero, a hard budget excluding expensive and unknown
candidates, no model assignment on code/approval nodes, immutable version guards,
cross-owner denial, exclusive claims/stale-result rejection, persisted failures,
new-process reload, explicit unsupported free text and safe draft-only exports.

Local browser artifacts are in `router/output/playwright/foundation-flow.png` and
`router/.playwright-cli/` (ignored, not required by lane tests). The screenshot was
visually inspected: synthetic status, recommendation, evidence and inactive
export are readable; no private account or credential information is shown.

## Reproduce the browser check

Start `make api`, `make worker`, `make ui` in separate terminals. Use a fresh
Playwright CLI session and take a new snapshot before each referenced action:

1. Open `http://127.0.0.1:5173`.
2. Click **Document triage**.
3. Click **Save workflow & find fixture stack**; wait for **Job: succeeded**.
4. Click **Inspect fixture evidence**; check the synthetic provenance disclaimer.
5. Click **Export inactive draft policy**; inspect the downloaded JSON.
6. Reload the saved `?job=...` URL; the workflow and recommendation should return.

No step calls a model or executes document processing. Evaluation deliberately
returns `not_run` rather than simulating an observed quality score.

## Verified access and blockers

See `../TOOLS.md` for exact discovery boundaries. Drive requirements read,
GitHub list, Vercel team/project reads and Bright Data session-status reads worked.
GitHub returned no repositories; no workspace Git remote exists. Exa is discovered
but execution is unverified. Neon discovery requires an organization ID; no
approved managed database was established. Supabase was not added as a second
provider. No existing design/deployment/provider configuration was found.

The planning attachment is missing, documented in `../requirements.md`.
The disk-write blocker was resolved (7.2 GiB available at resume). Docker still
reports an existing image-store I/O error. A local PostgreSQL recipe and dialect
migration are included, but **PostgreSQL was not run or claimed tested**. The
executed acceptance path uses an explicitly selected durable SQLite fixture file.
Do not ship publicly before real auth, authorized live adapters, PostgreSQL
verification and production hardening are complete.

Known foundation limits: intake/workflow/enqueue are separate writes and are not
deduplicated across resubmission; shared tenancy is not enabled; no deployment,
real catalog, real quality evaluation or arbitrary-language interpretation exists.
These limits do not prevent either lane's offline tests or frozen-contract work.

## Start both lanes later from the same commit

These are instructions only; they were **not executed**. From the repository root:

```sh
FOUNDATION_COMMIT=$(git rev-list --max-parents=0 codex/router-foundation)
git worktree add -b codex/router-intelligence ../Buildbox-Router-Intelligence "$FOUNDATION_COMMIT"
git worktree add -b codex/router-research ../Buildbox-Router-Research "$FOUNDATION_COMMIT"
```

`-b` refuses an existing branch; do not replace it with `-B`. Both destination
paths and suggested branch names were checked unused at handoff. Recheck before
starting. Do not overwrite an existing destination, branch or tag.

In each worktree, read `AGENTS.md` and `docs/parallel-plan.md`, then use that lane's
independent setup/test command. Each lane owns only its named implementation and
tests. Shared-contract/migration/manifest/UI changes must be requested from the
integration owner. Never import the sibling lane to bypass the boundary.
