# Buildbox Open-Weight Router

Give the system a workload, not a model name. Buildbox derives requirements,
selects model/deployment configurations, explains tradeoffs, and executes bounded
workflows through an explicitly enabled local sandbox.

## Quick start

Requires Python 3.12+, uv, Node 22.12+ and npm.

```sh
cd router
make demo
```

Open http://127.0.0.1:5202/?intelligence=1.
Test login: `fixture` / `synthetic-test-password`.
The command starts the UI, API, worker and synthetic upstream in an isolated
database. Ctrl-C stops it; restarting resets the demo without deleting prior data.

## Features

- Workload profiles, hard capability/privacy/cost/latency constraints.
- Task-specific evidence, normalized ranking, Pareto alternatives and explanations.
- Separate routing confidence and model-quality confidence.
- Single-model and multi-model DAGs, parallel specialists and synthesis.
- Validation, bounded escalation/repair, fallback and deployment health.
- Versioned sandbox policies, scoped keys, SSE, JSON and read-only tools.
- Persisted outputs, comparisons, all-attempt accounting and outcome feedback.
- Deterministic scenarios A–K, including Generate → Verify → Repair.

**Local sandbox, not production-ready.** Routing and execution software are real.
Demo responses, benchmark values and deployment facts are synthetic. Live model
quality is unverified. Publishing source does not authorize exposing the fixture
server to the internet.

## Organization

| Path | Contents |
|---|---|
| `router/backend/` | API, routing, planning, research and runtime |
| `router/web/` | Workflow studio and generated client types |
| `router/tests/` | Offline tests and synthetic transports |
| `router/scripts/` | Setup and verification utilities |
| `router/contract-fixtures/` | Shared executable-policy fixtures |
| `docs/` | Architecture, contracts and verification history |

`main` contains the complete integrated product and development history.
`milestones/*` preserves earlier development checkpoints, not missing features.
Credentials, local databases, dependencies, caches and build output are intentionally
excluded. Unrelated internship research is not part of this repository.

## Documentation

- [Architecture](docs/OPEN_WEIGHT_ROUTER_ARCHITECTURE.md)
- [API compatibility](docs/API_COMPATIBILITY.md)
- [Latest verification](docs/handoffs/12-advanced-local-sandbox.md)
- [Development setup](router/README.md)

The sandbox milestone passed 485 backend tests (including 180 gateway/runtime
tests), 14 frontend checks, API client checks and browser A–K acceptance.
See the verification handoff for exact scope and evidence limitations.
