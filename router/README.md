# Buildbox workflow router · offline foundation

One React/TypeScript UI, one FastAPI/Pydantic backend package, one worker, and a
PostgreSQL-compatible persistence layer. This is decision-support scaffolding,
not a live advisor or workflow execution engine.

## Run locally

Prerequisites: Python 3.12+, `uv`, Node 22.12+ and npm. Initial dependency installation
uses package registries; ordinary tests and the running fixture path require no
internet, provider credentials, credits or external services.

```sh
cd router
make setup
make migrate
```

Run three terminals, each from `router/`:

```sh
make api
make worker
make ui
```

Open http://127.0.0.1:5173. Select **Document triage**, save, wait for the worker,
inspect evidence and export an inactive draft. The job URL survives refresh.
The API's schema explorer is http://127.0.0.1:8000/docs.

Default durable storage is **explicit SQLite fixture mode**, `.local/router.db`.
No automatic database or live-to-fixture fallback occurs. `.env.example` documents
environment variables; the application does not silently load `.env` files.

## Local PostgreSQL

PostgreSQL is the intended deployment database. For a working Docker installation:

```sh
docker compose up -d postgres
export ROUTER_DATABASE_URL=postgresql+psycopg://router@127.0.0.1:55432/router_fixture
make migrate
make api
```

Export the same URL in the worker terminal. The isolated Compose database uses
trust authentication on a loopback-only port and must **never** be deployed.
Migrations use PostgreSQL SQL and an immutable-record trigger; SQLite has its own
equivalent trigger. Local PostgreSQL execution remains unverified while the host's
Docker image store reports I/O errors. No managed database was provisioned.

## Checks

```sh
make generate
make check
make test-intelligence
make test-research
npm audit
```

The integration suite includes durable reload in a new Python process, ownership,
immutable versions, graph validation, zero/unknown semantics, hard filtering,
job claims, evidence retrieval and safe draft exports. Tests use per-test temporary
databases and reject outbound socket connections. Browser procedure and results:
`../docs/handoffs/01-foundation.md`.

## Boundaries

- Only the unchanged example is interpretable; other text returns material
  clarification, not canned success. Constraints can be changed through the API.
- All catalog entries, costs and evidence are synthetic. Unknown latency/hardware
  is not converted into zero or a capability claim.
- Evaluation returns a persisted `not_run` result with an unknown metric; no
  invented score or paid model call. Ports are ready for controlled evaluation.
- Policies contain configuration references, not endpoint URLs or credentials.
  They stay `draft`, `active=false`, `production_write=false`.
- Workflow versions, recommendations, snapshots, evaluations and policies are
  append-only in the database. Job status is mutable with claim tokens and leases.
- Local fixture ownership is not multi-user auth. Shared and live modes refuse
  startup. Bind to loopback; never expose this foundation publicly.

Contracts and lane instructions live in `../docs/`. No lane is started by setup.
