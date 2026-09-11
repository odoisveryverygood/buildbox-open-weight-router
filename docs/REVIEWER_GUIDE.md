# Buildbox sandbox router — reviewer guide

September 10, 2026. This is an integrated local sandbox implementation, **not a
live-provider or production-readiness certification**. Start with the workflow
description, not a generic chat window. See [evaluation results](ROUTER_V2_EVALUATION.md)
and [API subset](API_COMPATIBILITY.md) for evidence and explicit limitations.

## Run the normal product locally

From the integration checkout's `router/` directory, use the existing stack:

```sh
make setup
ROUTER_DATABASE_URL=sqlite:///.local/integration9.db uv run python -m buildbox_router.storage
```

Run these in three terminals, using the same database:

```sh
ROUTER_DATABASE_URL=sqlite:///.local/integration9.db ROUTER_WEB_ORIGIN=http://127.0.0.1:5200 uv run uvicorn buildbox_router.api:create_app --factory --host 127.0.0.1 --port 8030 --no-access-log
ROUTER_DATABASE_URL=sqlite:///.local/integration9.db uv run python -m buildbox_router.worker
ROUTER_API_ORIGIN=http://127.0.0.1:8030 ROUTER_WEB_PORT=5200 npm run dev
```

Open **http://127.0.0.1:5200** on this machine. This is NOT a shareable preview.
Without a separately approved runtime registry, model calls remain blocked—never
silently replaced by fixtures. Local fixture identity is not authentication.

## Review the product journey

1. Describe a text workflow. Select the explicitly labeled one-model template
   option if no interpreter is configured. Try “Organize receipts,” then answer
   the requested input/output questions. Unknown hard requirements stay blocked.
2. Inspect the graph, deterministic versus model stages, assumptions, sourced
   catalog facts and candidate exclusions. Public discovery is not callability.
   The retained public snapshot has eight artifacts and zero approved targets.
3. Save the plan; prepare an executable draft. Inspect prompt and named bindings.
   Use structured edits or the documented bounded “make STAGE cheaper” instruction.
   Review the diff and confirm the new draft. Server selection is authoritative.
4. Import the same bounded examples for candidate policies. Explicitly review
   redaction, data class, processing consent and optional expected answers.
   The current API requires test policies to be sandbox-enabled before a costed
   comparison; it does not require pre-existing quality evidence. An API alias
   can be created after comparison. No automatic winner is selected.
5. Enable only the exact reviewed policy with a current operator-issued admission.
   Preview inputs/prompts before a sample run. A chat alias calls ONE LLM stage;
   `/api/sandbox/runs` executes the supported graph separately.
6. Inspect persisted stage outputs, attempts, decision trace, failures and usage.
   Reloading, refreshing or opening history never replays a model/tool call.
7. Create an immutable alias and a scoped application key. Copy the masked,
   one-time application key securely, hide it, then test/revoke it. It is NOT an
   upstream credential. Python/TypeScript/cURL examples reference environment
   variables and our API, not a direct-provider shortcut.
8. Change a pin, constraint or prompt. Confirm a new version; old runs/pins remain.
   Old admission cannot enable the new version. Inspect an older still-valid
   version and explicitly enable/disable versions for rollback; aliases never move.

## Reproduce the explicit synthetic acceptance test

This uses the same UI, API, worker, selector, contracts and guarded HTTP adapter,
but a **synthetic loopback upstream** and a fresh temporary database. Never deploy
this test factory. It provisions only synthetic test admissions; activation still
requires an explicit UI action. It is not the normal product runtime fallback.

```sh
ROUTER_ACCEPTANCE_SETUP=synthetic-public-only ROUTER_WEB_ORIGIN=http://127.0.0.1:5201 uv run uvicorn tests.gateway.browser_fixture:create_fixture_app --factory --host 127.0.0.1 --port 8031 --no-access-log
ROUTER_API_ORIGIN=http://127.0.0.1:8031 ROUTER_WEB_PORT=5201 npm run dev
```

Open **http://127.0.0.1:5201**. The PUBLIC TEST-ONLY Basic identity is `fixture`
with password `synthetic-test-password`. It grants no real provider access.
The factory owns its worker and temporary database; no third worker is needed.
Start a fresh factory for each complete automated acceptance run, since immutable
policy IDs and explicitly enabled versions persist for that factory lifetime.

`router/web/tests/browser_upgrade.js` is the Playwright CLI `run-code --filename`
script used against the authenticated page. It does not mock browser API responses.
It exercises a fixed public packet, four comparison cells, new version/admission
isolation, reload, alias creation, key issue/hide/revoke and mobile layout.

For the separate actual-HTTP client smoke test:

```sh
uv run python -m tests.gateway.client_smoke
```

It launches an isolated synthetic server, supplies ephemeral application keys via
subprocess environment, and runs Python, TypeScript and cURL against OUR endpoint.
No real upstream credentials, public search or billable calls are involved.

## Demo evidence on this checkout

Local generated artifacts are intentionally Git-ignored; recreate with the browser
script. These are actual screenshots/recording, not design mockups:

- `router/output/playwright/09-integrated-final.webm`: successful final browser flow.
- `09-comparison-results.png`: four returned outputs, schema checks and two visible
  exact-match failures, with measured local timing and synthetic $0 accounting.
- `09-public-packet-activity.png`: three persisted stage outputs, including retained
  source URL/locator/date. The generated answer is synthetic, not research quality.
- `09-routes-api.png`: explicitly enabled version and immutable single-stage alias.
- `09-mobile.png`: real activity at a 390-pixel viewport, without horizontal overflow.
- `09-edit-diff.png`: earlier normal-product draft/prompt diff inspection.

## Secure operational onboarding / deployment blocker

No approved managed secret store, two real eligible target configurations, target
spend cap, selected hosted backend/database or preview deployment target was supplied.
Nothing was pushed, provisioned or deployed. A frontend-only deployment is not
completion. Existing host allowlisting is loopback-only; shared preview additionally
needs central host/TLS/backend-streaming/worker/retention review.

When approval exists, the operator—not model output or an import—must provision a
private canonical `RuntimeRegistry`, exact evidence-backed targets/catalogs, budget,
scoped grants/admissions, approved endpoints, credential references and server-side
secret environment bindings. Use the already approved secret-storage mechanism;
do not paste keys into chat, the UI, source files or frontend environment variables.
Set identical approved runtime/auth configuration on API and worker. See
`API_COMPATIBILITY.md` and `router/INTEGRATION_RUN.md` for existing secure identity
provisioning and fail-closed configuration. Do not fabricate admissions to unblock
a test. Connector availability does not grant any of these operational permissions.

Remaining product limits: general NL multi-tool DAG interpretation still needs an
authorized interpreter or reviewed explicit graph; no runtime web search; human
pauses cannot resume; free-form semantic rubric execution and first-content timing
for nonstream workflows are unsupported. Real two-model quality comparison and
protected preview acceptance remain NOT RUN.
