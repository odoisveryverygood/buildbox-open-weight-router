# Buildbox router — development

FastAPI/Pydantic backend, React/TypeScript studio, a bounded workflow worker, and
SQLite fixture or PostgreSQL persistence.

## Complete local sandbox

```sh
make demo
```

Open http://127.0.0.1:5202/?intelligence=1.
Test login: `fixture` / `synthetic-test-password`.
Original scenarios are at `/?demo=1`. Upstream responses are synthetic;
no paid credentials are required. Restart for a fresh isolated database.

For alternate ports:

```sh
BUILDBOX_DEMO_API_PORT=8038 BUILDBOX_DEMO_WEB_PORT=5208 make demo
```

## Development and checks

Requires Python 3.12+, uv, Node 22.12+ and npm. From this directory:

```sh
make setup
make migrate
make check
node web/tests/unit.cjs
uv run python -m tests.gateway.client_smoke
```

For separate development services, run `make api`, `make worker`, and `make ui`
in separate terminals. UI: http://127.0.0.1:5173; API schema:
http://127.0.0.1:8000/docs. This default composition does not grant live inference;
use `make demo` for fully seeded synthetic execution.

`.env.example` documents configuration; environment files are not silently loaded.
Tests use isolated databases and deny external network calls; selected transport
tests explicitly allow one synthetic loopback server. Native PostgreSQL clean and
v2→v5 upgrade checks passed. Never run clean-database checks against application data.

## Boundaries

Keep test services on loopback. Real execution requires scoped authorization,
approved provider targets/credentials, capability and privacy checks, license/access
evidence, and bounded spending. Unknown charges remain unknown. Unreviewed tools,
arbitrary code execution and production activation remain blocked.

[Architecture](../docs/OPEN_WEIGHT_ROUTER_ARCHITECTURE.md) ·
[Latest verification](../docs/handoffs/12-advanced-local-sandbox.md)
