# Buildbox workflow router — upgrade foundation

## Active integration milestone 09

The user authorized central shared-contract/API/storage/worker and runtime/studio
integration on `codex/router-v2-integration`, based on Prompt 6 commit
`48ba6e2b2dc7d7d509cc68e2314c89dd5c54fec0`. Preserve commits from both lanes and
the subsequent central 7B integration; their
exclusive ownership rules below remain historical lane boundaries, not a block on
this integration task. Read `docs/handoffs/09-router-v2.md`,
`docs/REVIEWER_GUIDE.md` and `docs/API_COMPATIBILITY.md`. No production merge/deployment,
new provider authorization, secret discovery or implicit fixture/live fallback.

The implementation lives in `router/`. Existing `.agents/`, company research,
`final-synthesis/`, `openrouter-research/`, and prior deliverables are unrelated user
work: do not modify or stage them for router commits.

## Safety and scope

- Read `docs/requirements.md`, `docs/contracts.md`, `docs/TOOLS.md` and
  `docs/parallel-plan.md` before implementation.
- Read `docs/upgrades/router-v2.md` for the current frozen upgrade interfaces,
  lane paths, isolation and acceptance gates. Handoffs 01–04 are historical,
  not proof that milestone 05 or live execution was completed.
- The September 7 upgrade permits **controlled sandbox execution** in later
  implementation lanes. Describe → clarify → propose stages/tools/configurations
  → edit → compare outputs → enable a sandbox route → run → inspect usage remains
  the product. Do not replace it with a generic chat UI.
- Draft, sandbox-enabled and disabled are separate versioned states. Sandbox
  activation is NEVER production approval. Production writes, autonomous business
  actions, arbitrary shell/code, unregistered tools and production routing remain
  prohibited. Existing planning/DraftPolicy records never become executable.
- Untested quality is allowed only with a visible provisional label. It cannot
  waive verified privacy, authorization, license/access, capabilities, budgets,
  hard constraints or guarded egress. Never require an eval before the first
  sandbox test merely to satisfy a quality label.
- No billable inference/search, cloud provisioning, deployment, production writes,
  credential discovery, or copying session credentials without new authorization.
- Preserve unknowns and provenance; synthetic facts are never real catalog entries.
- Local identity is `local-fixture-user`, not authentication. Shared/live execution
  must use the verified auth boundary and server-side approvals. Synthetic gate
  fixtures are not operational admissions; no HTTP grant-creation endpoint.
- The existing planning local-model/public-metadata opt-ins remain scoped to
  planning. They do not authorize hosted target inference or customer-data egress.
- Keep imported samples/outputs tenant-private with expiry, separate from immutable
  public research and audit metadata. Ordinary tests use no credentials or network.
- Do not create credential-dependent clients at import time.

## Ownership (current lanes, not launched by milestone 06)

- Lane 7 owns `router/backend/buildbox_router/gateway/`,
  `router/tests/gateway/`, and its handoff/change-request notes. Gateway services,
  target runtime adapters, runner, dispatcher, app-key auth and runtime accounting
  orchestration live there. Use shared persistence/security, not new tables/contracts.
- Lane 8 owns `router/web/src/` EXCEPT `generated/`,
  `router/backend/buildbox_router/research/`, `router/tests/research/`,
  `router/tests/studio/`, `router/web/tests/`, and its handoff/change-request notes.
  Do not edit the separate internship/company corpus or target selection code.
- Integration owner owns contracts, ports, migrations, storage, API/composition,
  inference transport, shared fixtures, UI, generated types, manifests/lockfiles,
  root instructions and deployment. Neither lane edits these shared files.
- Lane code imports shared contracts/ports, never the sibling implementation.
  `execution_contracts.py`, `execution_ports.py`, `execution_security.py`,
  `execution_storage.py`, `execution_api.py`, `openapi_schema.py`, existing
  `runtime.py`/`local_inference.py`, and `contract-fixtures/` are integration-owned.
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
Do not start either lane merely because its handoff exists. Milestone 06 prepares
lanes 7/8; only a subsequent user request authorizes starting them.
