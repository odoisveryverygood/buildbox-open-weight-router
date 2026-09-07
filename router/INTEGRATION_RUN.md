# Planning alpha: local operation and boundaries

Run from `router/`. Python 3.12 and Node/npm are required. No deployment or migration
runs automatically. Install dependencies with `uv sync --frozen && npm ci --ignore-scripts`.
Run `make check` for offline tests, both type checks, lint, build and generated-type drift.

## Fixture application

Use three terminals after the explicit migration. These ports avoid the foundation
application already running on 8000/5173 during integration.

```sh
ROUTER_DATABASE_URL=sqlite:///.local/integration-clean.db uv run python -m buildbox_router.storage
ROUTER_DATABASE_URL=sqlite:///.local/integration-clean.db ROUTER_WEB_ORIGIN=http://127.0.0.1:5184 uv run uvicorn buildbox_router.api:create_app --factory --host 127.0.0.1 --port 8014 --no-access-log
ROUTER_DATABASE_URL=sqlite:///.local/integration-clean.db uv run python -m buildbox_router.worker
ROUTER_WEB_PORT=5184 ROUTER_API_ORIGIN=http://127.0.0.1:8014 npm run dev --workspace web
```

Visit http://127.0.0.1:5184. Extraction and support examples produce synthetic
configuration mappings and inactive policy downloads. Company research produces a
bounded graph with a blocked mapping: exact tool-call capability is unverified.
Image, self-host, structured-output and model-tool-call requirements fail closed
when evidence is missing. Explicit code-only text transformations use no model.

The public snapshot is retained September 6 evidence, not a new network lookup:
8 artifacts, 17 captures, and no verified runnable configurations. Runtime public
research instead fetches one fixed official Qwen repository metadata resource.
Neither path turns publisher declarations into tested configurations.

## Local runtime inference, without credentials or provider charges

Integration discovered an existing Ollama 0.32.5 installation and cached
`qwen2.5:0.5b`. No model was pulled or installed. The app checks `/api/tags` and
refuses missing/cloud models or cached models over 2 GB. Local interpretation is
explicitly selected in the form, is bounded to 1,400 output tokens/40-second HTTP
deadline, and never invokes tools. Complex tool/loop interpretation is unsupported
by this small local adapter; manual validated graphs and explicit fixture examples
remain available. Graph quality is uncalibrated and needs human review.

```sh
OLLAMA_HOST=127.0.0.1:11444 OLLAMA_NO_CLOUD=1 OLLAMA_NOPRUNE=1 OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 ollama serve
```

Add `ROUTER_LOCAL_INTERPRETATION_MODEL=qwen2.5:0.5b` to **both API and worker**
commands, then select the local cached model in the form. The local server uses
the existing cache; keep cloud disabled. Request logging must remain disabled.
No model recommendation is inferred from this control-plane choice.

## Authenticated local live mode

Provision your own identity interactively, never a checked-in test password:

```sh
mkdir -p .local
uv run python scripts/create_local_user.py --username planner --owner tenant-one --output .local/users.json
```

Set `ROUTER_IDENTITY_MODE=shared`, `ROUTER_AUTH_FILE=.local/users.json`, and
`ROUTER_MODE=live` on API and worker. Use a separate explicitly migrated database.
The browser's HTTP Basic challenge handles login; no credential is stored in the
React application or exported policy. Live mode rejects legacy fixture endpoints
and synthetic catalogs. All plan reads, revisions, cancellation and export bind
the authenticated tenant and exact plan version. HTTP Basic requires TLS before
any non-loopback use. No shared/public deployment is authorized by these checks.

## Hosted OpenRouter gate (not live-verified)

The installed credential-approval flow was not bypassed. No hosted key was found,
copied, created or spent from. Selecting hosted interpretation cannot grant
server permission. `ROUTER_APPROVALS_FILE` must point to operator-approved role
records conforming to `runtime.RoleApproval`, with a real permission reference,
tenant, expiry, exact model and **qualified endpoint tag**, server key environment
name and dollar cap. Do not manufacture approvals just to enable the adapter.

Roles `interpretation` and `research` can have separate records/models/provider
endpoints/keys. Research currently uses deterministic public parsers and does not
require a model at all. Local interpretation and OpenRouter interpretation are
separate control-plane options. The runtime never consults Codex credentials.

OpenRouter checks endpoint metadata and required parameter support, restricts
`only` and `order` to the exact qualified tag, disables fallback, and requires
parameter support, denied data collection and ZDR. Pricing must fit supported
components and pre-reserved caps. Base provider slugs and generic auto routers are
not accepted. Retained metadata distinguishes requested endpoint from actual
provider/model/usage; chat responses do not attest an exact served endpoint.
Timeouts, incomplete accounting and worker recovery after any paid reservation
require reconciliation, not automatic repeated work. Budget holds are conservative
and are not refunded automatically. Hosted behavior is offline-tested, **not a
verified live integration**.

Official references inspected September 6:
[OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection),
[endpoint metadata](https://openrouter.ai/docs/api/api-reference/endpoints/list-all-endpoints-for-a-model),
[Ollama chat](https://docs.ollama.com/api/chat),
[Ollama structured output](https://docs.ollama.com/capabilities/structured-outputs).

## Browser checks

With the app running and the Playwright CLI available:

```sh
playwright-cli --session router open http://127.0.0.1:5184
playwright-cli --session router snapshot
playwright-cli --session router run-code --filename scripts/browser_checks.js
playwright-cli --session router run-code --filename scripts/browser_local_runtime.js
playwright-cli --session router console warning
playwright-cli --session router requests
```

`browser_checks.js` includes one real public metadata request. It is not an offline
CI test. `browser_local_runtime.js` also runs actual local inference and must be
invoked intentionally. The ordinary pytest suite denies network connections.
`scripts/browser_fault_server.py` is explicitly test-only: it injects a timeout at
the provider boundary while preserving the real API, worker, authentication and
database. `browser_failure_auth.js` verifies this isolated test deployment on
5185, including reload, cancellation and cross-tenant denial. Its public synthetic
test identities must never be used for deployment. It needs an explicitly migrated
isolated DB and authentication file; it never creates either automatically.

## PostgreSQL check

Use an independently initialized UTF-8 cluster bound to loopback, with a fresh
empty database. Do not point the check at an existing database. The script refuses
a nonempty public schema and runs explicit migrations and a persistence/concurrency
check; it is intentionally outside offline CI.

```sh
ROUTER_DATABASE_URL=postgresql+psycopg://buildbox_test@127.0.0.1:55484/buildbox_check uv run python scripts/check_postgres.py
```

## Release limits

There is no verified non-synthetic target configuration, calibrated language
understanding, completed evaluation, production routing, active policy, cloud
database, public deployment or customer workflow execution. Empty graph input
bindings are explicit planning gaps. The local model's observed malformed outputs
remain failed jobs; later successful infrastructure checks do not establish a
quality score. Qualification of real targets requires the next evidence/evaluation
milestone rather than weakening the selector.
