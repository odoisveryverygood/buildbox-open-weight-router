# Lane 7 integration requests — frozen 2.0 limits

Base: `48ba6e2b2dc7d7d509cc68e2314c89dd5c54fec0`. No shared files changed.
These are requested interface changes, NOT implemented features or approvals.

## R7-1: guarded streaming transport and terminal accounting (blocking)

`runtime.guarded_request` and `local_inference.local_request` return a fully buffered
JSON dictionary. `RuntimeInferencePort.stream` can yield only chunks/errors: no
actual cost, served identity, cancellation acknowledgement or final reconciliation.
The HTTP wrapper commits headers before iterating GatewayPort and its cancellation
callback checks time, not disconnect. Returning buffered text as token streaming
would violate the request. A second transport copied inside the lane would violate
the explicit shared-transport boundary in router-v2.md.

Proposal: integration-owned guarded async byte stream with an explicit response
handle, validated status/content type, pinned DNS/TLS, no redirects, bounded
frames/bytes/deadline, disconnect-aware cancellation and close; canonical terminal
inference observation containing usage/cost/identity facts separately from deltas.
Add a preflight/open response boundary before HTTP commits. Enforce total-frame
limits and fail on HTTP-200 error events. Cancellation acknowledgement must not
imply stopped billing. Add a canonical `partial_failure` error code.

Executable examples: `test_no_buffered_streaming_adapter` proves unsupported
transport rejects without upstream work; `test_stream_terminal_usage_pending`
proves frozen streaming cannot reconcile actual cost. Lane includes incremental
SSE framing tests, but no network SSE adapter is marked implemented/live-tested.
Compatibility: additive internal port with API regeneration; no migration needed
for a terminal usage record unless observation/timing fields are added.

## R7-2: supported chat tools/formats, direct configuration selection and variants

`ChatCompletionRequest` forbids tools/tool_choice/response_format and direct model
identifiers; ChatMessage excludes `tool`, IDs and tool-call results; CompletionDelta
excludes tool deltas. `ChatCompletionChunk.choices` cannot be empty for usage-only
chunks. These cannot be supported by hidden fields, a second schema, or silently
dropping data. `test_unsupported_contract_rejected_before_transport` and the HTTP
test demonstrate the current 400 boundary.

Proposal: versioned subset expansion in canonical contracts, including discriminated
tool requests/results/deltas, response-format modes and explicit buffered strict
validation semantics. Add configuration-versus-alias addressing with identical key
authorization and admission. Add server-pinned session/version binding (not a
client-supplied provider override), allowed fallback pins with complete gate checks,
bounded repair/retry records, and an explicit policy-variant contract. Frozen
ExecutableStage allows one configuration and zero retries; the existing Selector
port has no quality/balanced/cost mode, benchmark-scoped quality, or variant output.
Lane uses injected Selector.filter for hard eligibility but does not invent three
different quality rankings from the same cost-only fixture data.

Tests for tool round trips, strict JSON delivery/repairs, fallback dispatch and
session rebinding must be added after this expansion. Their success is not claimed.
Compatibility: wire contract generation and versioned new policy records; never
repin old aliases or convert v1 DraftPolicy into authority.

## R7-3: exact approved targets, freshness and tokenizer/price envelopes

ProviderCredentialReference allows only openrouter/local_ollama. LocalDeployment
has no admin endpoint ID and the shared transport pins Ollama to 127.0.0.1:11444.
No approved direct-provider or OpenAI-compatible local endpoint record exists.
Proposal: central administrator-owned endpoint registry, approved transport kind,
exact target/IP/path/TLS and credential references, with narrow local exceptions.
Never accept arbitrary client base URLs or weaken the public-source guard.

Authority takes server-injected target/grant/credential/catalog resolvers using
existing canonical types. Before operational composition, integration must define
durable provisioning/lookup conventions and freshness checks for those resolvers.
TargetConfiguration currently lacks an expiry and approved tokenizer/framing bound.
Its general admission capability/spending facts are not automatic evidence that
every tokenizer obeys this lane's conservative UTF-8 byte + message-overhead envelope.
Require an approved target-specific envelope/tokenizer and price completeness
evidence for hard-cap operational admission. Current hosted subset rejects unknown
conditional/extra prices and nonzero request surcharges, sets provider max_price
for prompt/completion, and retains conservative reservations. No live budget
guarantee was validated.

Compatibility: central endpoint/capability evidence expansion; update generated
clients once. Ollama adapter implemented here is a native second transport, NOT
the requested second OpenAI-compatible provider and NOT a live-tested provider.

## R7-4: app-key product flow and persisted limits

ApplicationKeyPort has authenticate/revoke only; metadata has no limit fields;
shared API has no issuance/revocation product routes. Lane exposes a studio-context
`ApplicationKeys.issue` returning metadata plus a once-only random secret. It
stores only PBKDF2 verifiers and independent immutable key budget caps. Rate windows
use the existing atomic budget table and a server-configured limit, not a new schema.
The raw secret must never be added to a handoff, log, trace or provider request.

Proposal: canonical issuance request/once-only secret response with non-repr secret,
authenticated product route with no app-key self-escalation, persisted per-key rate
policy and visible cap metadata; transactionally create verifier + cap. Add cleanup
for expired rate windows. Current issue failure can leave an unusable orphan cap;
separate holds across key/global budgets are conservative, not atomic refunds.
Versioned revocation is durable; the tests verify actual verifier authentication.

## R7-5: worker, checkpoint transactions, retention, telemetry and comparison

Lane runner's bounded `submit` executes inline through the frozen port, with CAS
claiming and durable stage/run records. It introduces no second queue/platform.
Integration must wire a worker submission/claim hook for true asynchronous 202
jobs and a crash-reconciliation sweep: an interrupted running request currently
stays running and cannot redispatch. Crash windows between CAS and metadata writes
fail closed; they are not automatic recoverable queue claims. Persist checkpoint
references, run/event/attempt updates and shared key+global reservations atomically
where required. Add timing fields with explicit definitions to canonical traces;
there is no field here for selection rationale text, dispatch/first-token latency,
or repair/fallback timing. No hidden metadata fields or new tables were introduced.

Runner requires explicit expiring output retention; generic chat defaults to no
content retention and duplicate submissions return 409 without replay when content
was not retained. Input-free crash recovery cannot resume an unstarted queued
sample without a canonical expiring input reference. Current events replay persisted
observations; repeated polling is needed for future events. Human pause is terminal
under 2.0, not automatically approved or resumable. Only registered synthetic
read-only sample lookups execute, not the research lane's network adapters.

ComparisonPort still needs integration orchestration of actual runner results and
an aggregate reservation; lane did not return invented model-output comparisons.
The authenticated key product flow and operational default composition are also
uninstalled. Do not treat passing offline port checks as full product integration.

## R7-6: existing dependency advisories

`npm ci --ignore-scripts` and `npm audit --json` reported two high-severity entries:
`@redocly/openapi-core` via nested `js-yaml`, GHSA-2883-xcg3-v3hh (CPU exhaustion).
Integrator should update and verify the root lockfile; lane did not run audit fix
or modify shared dependencies. Advisory data was checked September 8, 2026.
