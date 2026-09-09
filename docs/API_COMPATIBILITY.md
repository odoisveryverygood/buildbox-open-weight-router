# Runtime API compatibility — 7B

This is an explicit Chat Completions **subset**, not universal OpenAI compatibility.
Canonical definitions: `router/backend/buildbox_router/execution_contracts.py`,
`json_contracts.py`, `execution_ports.py`; generated `router/openapi.json` and
`router/web/src/generated/api.ts`. Additional fields are forbidden, not discarded.
Additive execution-schema 2.0 fields preserve existing text requests and policy
digest defaults; database revision 4 adds the durable runtime queue.

## Authentication and model identity

- `GET /v1/models`: SUPPORTED for a valid Buildbox application key with
  `models:read`; returns only that key's available immutable stage aliases.
- `POST /v1/chat/completions`: SUPPORTED CONDITIONALLY on key scope, exact alias,
  enabled policy version, current operator admission/grant/credential, selector
  eligibility, endpoint capabilities and bounded spend. No arbitrary model ID,
  OpenRouter Auto, URL, provider key or client-defined provider override.
- An explicit configuration is exposed by creating an immutable stage alias with
  that configuration pinned. Raw configuration IDs are not another authority path.
- Studio uses the existing authenticated Basic/session context on loopback/TLS;
  it issues/revokes independent application keys. Only salted PBKDF2 verifiers are
  stored. Newly issued secrets appear once, password-masked in UI, never localStorage.
  Scope, exact alias/policy lists, expiry, revoke, 30 requests/minute server limit,
  independent key cap and operator cap all apply. Issuance cannot grant admission.

## Every accepted chat parameter

| Parameter | Classification | Behavior / condition |
|---|---|---|
| `model` | SUPPORTED CONDITIONALLY | Required tenant/key-authorized immutable alias, pinned policy version and stage configuration. |
| `messages` | SUPPORTED CONDITIONALLY | 1–32 text messages; roles system/user/assistant/tool. Max 16,000 characters each, 64 KiB entire HTTP body. No multimodal content arrays. Policy instructions are prepended; caller system text is preserved as user text, not allowed to replace policy instructions. |
| `messages[].content` | SUPPORTED | String, or null/omitted only for an assistant tool-call message. |
| `messages[].tool_calls`, `tool_call_id` | SUPPORTED CONDITIONALLY | Declared tools, unique IDs, complete matching tool history. Tool results retain IDs. Caller supplies results; chat never executes tools. |
| `max_tokens` | SUPPORTED CONDITIONALLY | Required integer 1–16,384; smaller policy, effective context/output and approved token envelope limits also apply. No assumed default output budget. |
| `temperature` | SUPPORTED CONDITIONALLY | 0–2 only if the selected endpoint supports it. |
| `stream` | SUPPORTED CONDITIONALLY | Boolean; genuine incremental SSE on approved compatible targets. Native Ollama adapter remains nonstream text-only. |
| `tools` | SUPPORTED CONDITIONALLY | 1–8 function definitions, unique names, optional description, bounded strict `parameters` schema; `strict` must be true. Selected endpoint must support tools. |
| `tool_choice` | SUPPORTED CONDITIONALLY | auto / none / required / named function. Requires declared tools and endpoint support; returned calls/arguments checked. |
| `response_format` | SUPPORTED CONDITIONALLY | text, json_object, or json_schema with name, strict=true and bounded schema. Non-text formats require nonstream without tools; completed output is parsed/validated before delivery. No repair calls or fake token streaming. |

`JsonSchema` supports explicit object/array/string/number/integer/boolean/null types,
description, enum, properties, required, additionalProperties=false, items. Strict
objects require every property. Schemas are capped at 16 KiB; output validation
caps nesting at 20 and arrays at 10,000 items. `$ref`, unions/anyOf, regex/format,
additionalProperties=true, numeric/string range keywords and other keywords are
REJECTED. Invalid JSON, duplicate keys and non-finite numbers are rejected.

All other chat fields are REJECTED, including `n` (even 1), `stream_options`,
`max_completion_tokens`, `top_p`, `stop`, seed, logprobs/top_logprobs, penalties,
logit_bias, parallel_tool_calls, legacy functions/function_call, audio/images,
modalities, prediction, reasoning/service-tier controls, metadata/store/user,
provider/models/fallback overrides. Unsupported combinations are rejected before
upstream work. Explicit null optional fields mean unset, not provider instructions.

## Streaming, failures and accounting

SSE handles TCP/UTF-8 splits, multiple events/chunk, keepalive comments, content,
tool argument deltas/IDs, finish reasons and usage-only events. Terminal usage is
exposed with the final finish chunk; `[DONE]` is emitted only on a valid terminal
path. HTTP 200 upstream errors, malformed frames and missing terminal events fail.
First gateway event is prefetched before HTTP headers. Once any delta is exposed,
a failure produces `partial_failure` and no success `[DONE]`; no fallback/model
splicing or automatic tool replay occurs. Tool consumers must wait for successful
termination before treating streamed arguments as a complete validated call.

Fallbacks are distinct explicit policy pins (at most two), rechecked under the
same restrictions and aggregate attempt cap. Only before delivery, never arbitrary
upstream fallback. Conversation/tool requests require a **single-configuration**
alias: fallback aliases reject tools or multi-message histories, avoiding silent
session repinning. This is not a server-side conversation/session API.

Each possible attempt is conservatively bounded; unknown or extra-component
pricing blocks admission. Operator-verified endpoint token-envelope evidence is
required outside explicit software tests. Integer micro-USD reservations use
atomic conditional updates; concurrent calls cannot spend the same approved cap.
Actual usage is reconciled when known; ambiguous failure/cancel keeps its hold.
Invalid structured output still records available charge/usage. No refund or
upstream billing cancellation is promised. Same idempotency key never blindly
redispatches; default chat output retention is off, so replay can be 409.

Attempt latency is reservation-to-finalization wall time, not provider inference
time or time-to-first-token. Absent measurements remain null. Traces retain policy,
configuration, catalog/evidence, requested endpoint and safely observed served
identity, not prompts/outputs, secrets or chain-of-thought.

## Product, policies and worker

- `POST /api/studio/policies/{id}/versions/{v}/variants` creates a **new draft**
  using the pinned catalog and existing selector. Quality and balanced share the
  uncalibrated selector heuristic; cost-conscious prioritizes known normalized
  catalog token prices. No measured accuracy/savings claim. Fallbacks are omitted
  from compiled variants until separately pinned/approved; existing aliases never move.
- `POST /api/sandbox/runs` persists request, typed inputs, context and queue record
  atomically, returning queued. Existing `worker.run_once` claims the job, then
  reuses WorkflowRunner and Gateway. Deadlines/leases never authorize redispatch.
  Expired/crashed runs become uncertain; persisted checkpoints remain inspectable.
- Executable nodes: LLM with reviewed literal prompts and actual predecessor
  bindings; registered text operations; separately allowlisted sample lookup;
  human-approval pause. Explicit parallel dependency frontiers and shared caps.
  Bounded agents, arbitrary code, email/database/shell actions, unregistered
  external tools, and human-pause resumption remain unsupported. No declared tool
  grants execution permission. No production routing migration or activation exists.
- Comparisons submit the same worker runs, retain per-attempt reservations/output
  references and blocked/failed cells. No synthetic score, automatic winner or
  fabricated aggregate reservation. Output completion is not quality validation.
- Studio runtime/key metadata, workspace workflow-run listing (up to 1,000), exact
  run attempts, events, outputs and traces are real persisted state. Lists are
  bounded, not an exhaustive billing/analytics export. Refresh is read-only.

## Installation and privacy

Both app and existing worker read `ROUTER_RUNTIME_REGISTRY_FILE`, a private,
operator-controlled canonical `RuntimeRegistry` JSON file. Shared identity and
explicit `ROUTER_MODE=live` (never fixture mode), plus
current exact target/catalog/credential/grant/admission/budget/endpoint records are
required. Secret references resolve only administrator-named environment variables
at dispatch. No credential discovery, session-key copying, or automatic fixture
fallback. Registry replacement cannot alter policy content or alias pins.

`ApprovedEndpoint` permits public HTTPS:443 with public DNS/IP checks and pinned
TLS, or explicit literal loopback IP + port + `/v1/chat/completions`. No redirects,
userinfo, query credentials, arbitrary intranet targets or private DNS exceptions.
Native Ollama remains fixed to its previously approved local target. Generic
compatible endpoints do not receive OpenRouter-only controls.

Workflow execution needs explicit `ROUTER_RUNTIME_RETENTION_SECONDS` (default one
hour; max 30 days) for checkpointed outputs. Queue inputs expire after 120 seconds
and are deleted on completion or expired-queue cleanup. Existing output/import
expiry rules apply; local storage is not claimed encrypted at rest. Deployment,
managed secret operations, encryption/backups and broader security review remain gated.

OpenRouter requests pin a model and allowed endpoint tag, disable opaque fallbacks,
require parameters and deny data collection with ZDR. These rely on upstream
enforcement, not Buildbox-owned serving. Current official references inspected:
[provider routing](https://openrouter.ai/docs/guides/routing/provider-selection),
[streaming](https://openrouter.ai/docs/api/reference/streaming), and
[structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

**LIVE INFERENCE NOT VERIFIED. LIVE SECOND PROVIDER = UNVERIFIED.**
Only explicit synthetic loopback HTTP and recorded OpenRouter fixtures were run;
no authorized registry, provider key or target grant was supplied in this session.
