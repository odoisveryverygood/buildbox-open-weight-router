# Buildbox router foundation

The implementation lives in `router/`. Existing `.agents/`, company research,
`final-synthesis/`, `openrouter-research/`, and prior deliverables are unrelated user
work: do not modify or stage them for router commits.

## Safety and scope

- Read `docs/requirements.md`, `docs/contracts.md`, `docs/TOOLS.md` and
  `docs/parallel-plan.md` before implementation.
- This milestone is offline and synthetic. Never execute a described workflow,
  connect an execution tool, send customer data to a provider, or activate a policy.
- No billable inference/search, cloud provisioning, deployment, production writes,
  credential discovery, or copying session credentials without new authorization.
- Preserve unknowns and provenance; synthetic facts are never real catalog entries.
- Local identity is `local-fixture-user`, not authentication. Shared/live modes must
  fail closed until the integration owner approves and tests real adapters.
- Do not create credential-dependent clients at import time.

## Ownership

- Lane 2 owns only `router/backend/buildbox_router/intelligence/` and
  `router/tests/intelligence/` (plus its handoff/change-request notes).
- Lane 3 owns only `router/backend/buildbox_router/research/` and
  `router/tests/research/` (plus its handoff/change-request notes).
- Integration owner owns contracts, ports, migrations, storage, API/composition,
  inference transport, shared fixtures, UI, generated types, manifests/lockfiles,
  root instructions and deployment. Neither lane edits these shared files.
- Lane code imports shared contracts/ports, never the sibling implementation.
- If a frozen contract needs changing, write a lane-local change request with
  rationale, compatibility impact and a failing test/example. Do not patch it.
- Use separate worktrees and isolated local databases/caches. See the parallel plan.

## Validation and handoff

From `router/`: `make setup`, `make generate`, `make check`.
After changing canonical contracts, regenerate OpenAPI/TypeScript and verify no
generation drift. Never hand-maintain frontend API schemas.

Each lane handoff must name its base commit, files changed, executed commands and
results, contract requests, security/spend boundaries, and remaining unknowns.
No unexecuted check may be marked passed. No pushing/protected-main changes.
Do not start either lane merely because its handoff exists.
