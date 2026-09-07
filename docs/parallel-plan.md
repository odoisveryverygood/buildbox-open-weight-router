# Parallel ownership handoff

**Historical lanes 2/3 below are integrated. For current lanes 7/8 use
`docs/upgrades/router-v2.md` and `docs/handoffs/06-upgrade-base.md`. Do not restart
the old lanes or create new worktrees from the foundation commit.**

Both lanes start from the **same foundation commit**, resolved in
`docs/handoffs/01-foundation.md`. No lane has been started, branched or delegated.

| Boundary | Owned paths | Suggested branch |
|---|---|---|
| Lane 2: workflow interpretation, clarification, filtering/ranking/stack selection, safe policy compilation | `router/backend/buildbox_router/intelligence/**`, `router/tests/intelligence/**`, `docs/handoffs/02-intelligence.md`, `docs/change-requests/lane-2/**` | `codex/router-intelligence` |
| Lane 3: catalog snapshots, research logic, public-source adapter logic, public fixtures/evidence | `router/backend/buildbox_router/research/**`, `router/tests/research/**`, `docs/handoffs/03-research.md`, `docs/change-requests/lane-3/**` | `codex/router-research` |
| Integration owner | `contracts.py`, `ports.py`, `migrations/**`, `storage.py`, `api.py`, `composition.py`, `adapters.py`, `worker.py`, `config.py`, generated schemas/types, shared tests/fixtures, UI, all manifests/lockfiles, instructions and deployment | `codex/router-foundation` or later integration branch |

## Lane 2 starting brief

Implement richer interpretation and material clarifications behind `Interpreter`
and `Clarifier`; improve selection and policy explanations through frozen typed
inputs. Work against lane-owned synthetic catalog fixtures, not Lane 3 imports.
Do not represent fixture parsing as an arbitrary language model. Keep actions
descriptive, graph validation strict, non-model nodes unassigned, and exports
inactive. Request inference or schema changes from the integration owner.

```sh
cd router
UV_CACHE_DIR=.local/cache-lane2 uv sync --frozen
uv run pytest tests/intelligence -q
uv run ruff check backend/buildbox_router/intelligence tests/intelligence
```

## Lane 3 starting brief

Build catalog/research handling and source evidence normalization behind
`CatalogPort`/`ResearchPort`, using injected `SearchPort`. Add recorded synthetic or
explicitly public evidence fixtures inside this lane. No broad collection, paid
search, client construction on import, copied research-private content or network
tests by default. Preserve artifact/config distinction and provenance; fixture
names never become real catalog entries. Research-job scheduling/composition stays
integration-owned; request changes rather than editing the shared worker.

```sh
cd router
UV_CACHE_DIR=.local/cache-lane3 uv sync --frozen
uv run pytest tests/research -q
uv run ruff check backend/buildbox_router/research tests/research
```

## Isolation and frozen interfaces

Tests create unique pytest temporary databases and deny outbound sockets. Lane
tests need no shared service, cloud database or sibling lane implementation. Each
worktree has its own `.venv`, `.local`, pytest temp directory and cache. For manual
integration use `.local/lane2.db` or `.local/lane3.db`, never the foundation DB.
If local PostgreSQL is later enabled, use separately created `router_lane2` and
`router_lane3` databases and distinct ports/Compose project names; do not reuse a
shared schema. No lane may create managed resources without authorization.

No shared files, root lockfile changes, generated-type edits or sibling imports.
File a change request in your lane's `docs/change-requests/` folder with the
interface delta, reason, compatibility/migration impact, fixture example and
tests. Wait for integration-owner delivery of the revised contract.

Handoff each lane with its exact base and final commits, owned files changed,
commands/results, recorded evidence provenance, remaining unknowns, and change
requests. Preserve offline/no-write boundaries unless explicitly expanded.
