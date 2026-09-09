# Router v2 — frozen sandbox upgrade boundary

**7B integration note:** the central integration branch has preserved both lane
histories and extended the shared boundary. Current runtime behavior and supported
subset are in `docs/API_COMPATIBILITY.md`; audit and results are in
`docs/handoffs/07b-runtime-unblock-plan.md` and `07b-runtime-complete.md`.
The milestone-06 scope/ownership below remains the historical lane starting contract,
not a statement that runtime ports or the studio are still unimplemented.

Milestone 06, September 7, 2026. Base: `a3f8c28ed42d461ed570800b7addcd2a4c487f36`.
The upgrade-base commit containing this document is the common lane starting point.
Resolve the final commit from `codex/router-upgrade-base` after its handoff. Do not
start from the older foundation or either old lane branch. **Lanes 7/8 are not started.**

## Product and audit

Keep the existing React/Vite + FastAPI/Pydantic + SQLAlchemy/PostgreSQL stack.
Describe workflow → clarify → propose stages/tools/model configurations → edit →
compare actual outputs → sandbox-enable a pinned route → call its single-stage API
or run the supported workflow → inspect outputs, decision traces and usage.

The selected internship checkout is still the old foundation. The newer integrated
alpha is in `Buildbox-Router-Integration`, with handoffs 01–04 and 250 passing tests
at audit. No separate milestone-05 handoff/commit was found in the available refs.
Absence of that artifact is not a claim about work outside this repository.

Actual browser audit on isolated ports 5196/8026 confirmed describe/processing
controls, fixture extraction planning, persisted progress, a synthetic model
mapping, version-2 corrections/reload, and inactive export affordance. The screen
honestly says bindings are unspecified and evaluation is not run. Code/tests show
public snapshot research, an opt-in public metadata worker path, local Ollama
interpretation and an unverified hosted OpenRouter adapter. Those planning
adapters remain intact; they are not target-workload execution adapters.

Missing before this upgrade: executable binding/prompt/operation contracts,
sandbox states/aliases, application keys, gateway, workflow execution, comparison
of real outputs, imported traces and runtime accounting UI. Existing comparison
is a synthetic configuration rationale, not a side-by-side model-output test.
The current milestone supplies the shared boundary, not the completed runtime/UI.

## Canonical files and exclusive ownership

Paths are relative to the repository root (implementation is under `router/`).

| Owner | Exclusive implementation paths |
|---|---|
| Lane 7 | `router/backend/buildbox_router/gateway/**`, `router/tests/gateway/**`, `docs/handoffs/07-runtime.md`, `docs/change-requests/lane-7/**` |
| Lane 8 | `router/web/src/**` **except `generated/**`**, `router/web/tests/**`, `router/backend/buildbox_router/research/**`, `router/tests/research/**`, `router/tests/studio/**`, `docs/handoffs/08-studio.md`, `docs/change-requests/lane-8/**` |
| Integration owner | All shared `*_contracts.py`, `contracts.py`, `ports.py`, `execution_ports.py`, `execution_security.py`, `execution_events.py`, `execution_storage.py`, `execution_api.py`, `openapi_schema.py`, API/composition, worker, auth/settings, storage/migrations, `runtime.py`, `local_inference.py`, generated types/OpenAPI, `contract-fixtures/**`, shared integration tests/scripts, manifests/lockfiles/Vite config, root docs/instructions, deployment and final integration |

`intelligence/**` remains read-only for both lanes. No sibling implementation
imports. Lane 7 may reuse `runtime.guarded_request` and `local_inference.local_request`
within their existing destination/security constraints; it must not replace the
working planning adapters with mocks or copy their transports into competing files.
Lane 8 public-source adapters live under `research/` and consume the same shared
fetch guard. Requests for broader URLs/stream transport go to integration.

Shared entry points:

- `execution_contracts.py`: additive `execution_schema="2.0"`; composes v1
  Workflow/CandidateConfiguration/Fact and central EndpointRecord. No duplicate
  public workflow, catalog or evidence schema.
- `execution_ports.py`: GatewayPort, RuntimeInferencePort, WorkflowRunnerPort,
  ToolDispatcherPort, ApplicationKeyPort, ComparisonPort, StudioRepositoryPort;
  typed RequestContext and explicit `ExecutionServices` injection.
- `create_app(..., execution_services=...)` is the integration hook. Default is
  **None**, so execution/comparison returns explicit 503, not fabricated success.
- `execution_api.py` owns HTTP wiring. Lane 7 implements the injected ports, not a
  second API application. Lane 8 uses generated clients/contract fixtures, not
  direct imports of `gateway/**` or hand-maintained wire types.
- `execution_storage.py` exposes immutable policy/alias/prompt records, state CAS,
  tenant-scoped expiring samples/outputs, request registration, reservations and
  reconciliation. Lane 7 orchestrates these primitives; it does not write migrations.
  Use `register_request`/`advance_request`/`request_state`, `save_run`/`latest`,
  `save_attempt`, `save_trace`, `save_event`/`events`, `save_comparison`,
  `save_application_key`/`key_record`/`revoke_key`, and private payload helpers.

## Isolated lane setup (instructions only)

Do not create these worktrees or start services until the user launches the lanes.
Check destination/branch/ports are unused; never use `git worktree add -B`.

| Lane | Suggested branch / sibling worktree | API / UI | SQLite / caches | Optional local PostgreSQL |
|---|---|---|---|---|
| 7 | `codex/router-v2-runtime` / `Buildbox-Router-V2-Runtime` | 8027 / 5197 | `.local/lane7.db`, `.local/cache-lane7`, `.local/pytest-lane7` | private cluster port 55497, DB `router_lane7` |
| 8 | `codex/router-v2-studio` / `Buildbox-Router-V2-Studio` | 8028 / 5198 | `.local/lane8.db`, `.local/cache-lane8`, `.local/pytest-lane8` | private cluster port 55498, DB `router_lane8` |

Each worktree has its own `.venv`, node_modules, browser session, generated scratch
outputs and cache. Set `ROUTER_DATABASE_URL`, `ROUTER_WEB_ORIGIN`, `ROUTER_WEB_PORT`
and `ROUTER_API_ORIGIN` explicitly; never use the integration/audit database or
ports 8000/5173. Existing native PostgreSQL is the verified database; no approved
Neon/Supabase project is configured. Do not provision cloud databases or a second
provider. Ordinary tests use pytest temporary SQLite and deny outbound sockets.

## Executable policy and state semantics

V1 Workflow remains a descriptive DAG. ExecutablePolicy pins its exact saved plan
and catalog and requires all nodes' bindings to be typed and complete. A changed
binding requires a new planning version first. Stages cover every node exactly once.
Prompt revisions are immutable literal `{{variable}}` substitution (no Jinja,
expressions, eval, code, recursive substitution or source-provided instructions).
Stage variables match input types and referenced predecessor output types exactly.
Prompts are embedded at exact revisions in the policy so later edits cannot alter it.

Sandbox 2.0 supports LLM, named deterministic text operations, explicitly
allowlisted deterministic sample-tool stages, and human-review pauses. It rejects
bounded-agent execution until a later explicit contract expansion. One LLM stage
is one model call; it cannot implicitly call tools. Initially implement only
side-effect-free synthetic sample lookup tools, never arbitrary network/business
tools. Declared WorkflowTool is NOT an authorized execution connection.

Budget: integer micro-USD, input/output token ceilings, model/tool-call limits,
deadline ≤120 seconds, zero automatic retries; global policy cap bounds the sum of
stage reservations. Stop on error, exhaustion, or cancellation before next dispatch;
human approval pauses rather than being automatically granted. No human-resume
endpoint is promised in this subset: review is a terminal sandbox pause for now.

New policy content version starts **draft**, transition sequence 1. Allowed changes:
draft → sandbox_enabled or disabled; sandbox_enabled → disabled;
disabled → sandbox_enabled only with a new explicit valid admission check.
Transitions append records and compare-and-swap the expected sequence atomically.
There is no production state. A new policy version does not change an old version's
status or alias. Disable each old version explicitly when intended.

Alias ID is tenant-local and permanently pins policy ID/version, LLM node ID and
configuration ID. No update/repoint endpoint. Create a new alias for a different
pin. Resolve the pin and current transition/admission at every request/dispatch;
never consult the latest planning recommendation or silently pick a fallback.

## Admission, identity and permission boundaries

Drafts are planning data, not authority. Server-only SandboxAdmission pins the
policy content digest, configurations, allowed tools, credential references,
operator authorization and budget reference, expiry, and evidence-linked checks
for privacy, license policy, weights access, capabilities and spending. Unknown or
false fails. Synthetic check facts fail in normal composition. The explicit
`offline_contract_test=True` storage constructor exists only for isolated tests
and is never selected by HTTP/settings or runtime configuration.

RuntimeGrant is separately scoped to **target_sandbox**, tenant, exact target
configurations, credential references, data classes, expiry and budget. Existing
interpretation/research RoleApproval records never authorize target calls. Lane 7
must resolve/recheck grants, credential ownership/expiry, hard constraints,
parameter support and budget before each dispatch, including stream starts and
sample comparisons. Admission alone cannot increase a provisioned budget.
Operators must issue these records after evidence review; no browser/API endpoint
lets source/model/client JSON create a grant, credential reference or admission.

Untested quality is deliberately admissible as `untested_provisional`; this is
not proven quality or production readiness. Do not block the first controlled
comparison merely because there is no prior evaluation. Keep strict production
recommendation semantics untouched; present sandbox candidates for exploration
separately from recommended production migrations. License, privacy, identity,
capability and spending unknowns are not quality unknowns and cannot be waived.

Studio uses the existing loopback fixture identity or provisioned HTTP Basic
tenant identity. `/v1` requires an application Bearer key when a runtime is
installed. `/api/sandbox` accepts verified app keys or the existing studio identity;
keys are scope- and exact-alias/policy-allowlisted, expiring and revocable.
ApplicationKeyPort must verify the secret against a cryptographic verifier, never
trust just metadata/prefix. Store only a salted verifier and metadata; return any
new raw key once through a dedicated Lane 7 issuance flow, never in logs/traces.
ProviderCredentialReference stores only an opaque server secret reference; do not
copy Codex credentials or put a provider key in a client bundle.

Current HTTP routes supply RequestContext from verified server identity, a generated
request ID, bounded idempotency key, deadline and cancellation check. Runtime ports
must recheck identity/resource ownership for reads/cancels/events and stop dispatch
after disconnect/cancellation; an already-dispatched call may still incur usage.
Shared/public use needs TLS and operational identity/secret/retention review.

## HTTP subset and unsupported fields

This is an intentionally small compatibility surface, not a claim of full OpenAI
SDK/API compatibility. Official chat/model-list documentation was checked Sept 7:
[Chat API](https://developers.openai.com/api/reference/resources/chat),
[model list](https://developers.openai.com/api/reference/resources/models/methods/list).

- `GET /v1/models`: list only this key's authorized, usable sandbox **aliases**.
- `POST /v1/chat/completions`: `model` is an alias, `messages` are text-only
  system/user/assistant messages, required bounded `max_tokens`, optional
  `temperature`, optional boolean `stream`. Exactly one selected stage/config.
  It never invokes the workflow DAG or ToolDispatcherPort. Messages are stage
  input: adapters must prepend the pinned stage instruction and keep caller text
  below its authority; caller system messages cannot change control-plane policy.
- Reject all other parameters explicitly (400 `unsupported_parameter`), including
  tools/tool_choice, functions, provider overrides, n, response_format, multimodal
  content, seed, logprobs, reasoning fields, max_completion_tokens, response storage
  and fallbacks. Malformed supported fields return 400 `invalid_request`.
- Provider capability restrictions still apply to allowed parameters: requesting
  temperature on an endpoint without support must fail, not silently drop it.
- Nonstream returns one `chat.completion`; stream returns JSON `data:` frames of
  `chat.completion.chunk`, followed by `[DONE]`. Errors terminate the stream with
  sanitized error data; partial output never establishes a successful run.
  `X-Request-ID` joins the private trace; `X-Buildbox-Quality` shows provisionality.

Separate workflow endpoints: `POST /api/sandbox/runs`, `GET /api/sandbox/runs/{id}`,
`POST .../{id}/cancel`, `GET .../{id}/events?after_sequence=N`. Workflow SSE has
typed run.status/run.usage/run.error events, durable increasing sequence IDs and
replay cursors. A replay never executes work. Lane 7 must reject sequence gaps,
wrong run IDs and duplicate/conflicting observations before persistence.
API-key callers read expiring results through
`GET /api/sandbox/runs/{id}/outputs/{output_id}` and decision traces through
`GET /api/sandbox/traces/{request_id}` with `runs:read` and exact resource scope.

Working studio persistence endpoints: `/api/studio/policies`, exact policy-version
reads/transitions, `/aliases`, `/prompts`, `/imports`, `/outputs`, `/traces`.
Comparison endpoints use ComparisonPort and are 503 until installed. Completed
comparison cells require actual run/output/usage references; fixture outputs and
imported expected outputs never become measured model results.

## Accounting, persistence, private data and failures

Migration 3 is explicit and forward-only. It preserves v1/v1.1 rows and adds:
`sandbox_records` (tenant-local immutable metadata), `sandbox_heads` (CAS state),
`sandbox_budgets`, `sandbox_reservations`, `sandbox_requests`,
`application_key_verifiers`, and expiring `sandbox_payloads`. No service auto-migrates.
Private inputs/outputs stay in the deletable payload table, not immutable evidence
or audit rows. Imports retain original observation time as unknown if absent;
import time is server-assigned. Expired payload reads fail; explicit purge deletes
only expired payloads. Local storage is not a claim of managed encryption-at-rest;
review encrypted storage/backups before shared/private customer deployment.

Register idempotency before dispatch: same key+same content returns the saved run;
same key+different content is a conflict. A reused reservation never redispatches.
Hash input together with the exact policy/alias/prompt/config, operation and relevant
request parameters, never private plaintext in a request key. Lane 7 owns queue
state/CAS orchestration through these shared methods; it must not introduce its
own SQL schema. Queued requests can be claimed exactly once. Running requests can
be terminal or paused; uncertain/terminal requests cannot be automatically restarted.

Reserve worst-case call cost atomically against provisioned tenant/global budget
before transport, accounting for every pricing component and unit. Apply request,
stage and comparison aggregate limits too. Unknown prices cannot become zero.
Local no-provider-charge calls still obey call/token/deadline limits and are not a
claim of zero infrastructure cost. Keep missing usage unknown, not zero. Holds
remain conservative after cancellation/errors; no automatic refund. Overage
freezes remaining budget and requires reconciliation. Do not retry uncertain
dispatch after worker restart or SSE disconnect. Persist attempts, actual served
identity facts and accounting before exposing success; metadata opacity stays unknown.

Shared fetch protections stay in `runtime.guarded_request`: exact HTTPS allowlist,
path/method limits, public DNS/IP checks, pinned connection with TLS hostname,
redirect rejection, bounded response and timeout/cancellation callbacks. No arbitrary
URLs, business tools or private workload text enter public search. Source content
is data; it cannot change tools, rules, permissions, budgets or publication authority.
Bright Data/Exa connectors remain development tools, not runtime authentication.

## Lane acceptance and integration procedure

Lane 7: implement the frozen ports under `gateway/`; actual single-stage inference,
sample DAG runner, tool dispatch allowlist, tenant key verification/revocation,
bounded calls/cancellation/SSE, durable attempts/idempotency/accounting; no paid
live smoke without recorded provider/target/data/spend approval. Existing local
cached-model planning permission is not target-workload approval.

Lane 8: extend `PlanningApp.tsx` rather than replacing workflow intake; stage/prompt
editing, candidate cards with source/unknown facts, explicit provisional sandbox
state, comparisons/imports/API examples/run outputs/usage. Catalog work targets
exact publisher releases and provider-specific configurations; no fake rankings,
no metadata-as-workload-accuracy claim. Reuse retained public fixtures; refresh only
approved relevant stale/missing public facts through shared transport.

Both lanes: use generated `web/src/generated/api.ts` and
`contract-fixtures/sandbox-policy-v2.json`; the latter is synthetic, not an eligible
model or operational permission. Tests cover invalid inputs, tenant isolation,
version pinning, failure/partial/unknown states and no private-data leakage.
Run lane tests plus `make check`. Shared changes require a lane-local request with
example, compatibility/migration impact and failing test; integration supplies them.
Do not hand-edit generated types, change manifests, install new runtime dependencies,
reuse dev databases or touch Founding Customer Radar/unrelated internship research.

Final integration owner composes real ports, verifies full workflow/UI and approved
runtime checks, regenerates clients once, and reviews security/spend/retention.
Each lane handoff lists exact base/tip, files, executed checks, adapter readiness,
permissions and blockers. No push, deploy, production activation or quality claims.
