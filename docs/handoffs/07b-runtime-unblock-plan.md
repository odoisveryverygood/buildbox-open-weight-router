# 7B — central runtime unblock plan

September 8, 2026. Implementation branch: `codex/router-integration`.
Inspected baseline integration `a3f8c28`, runtime implementation
`06729065267879cbbebe57df5686d518f81b9d23` / tip
`027b950835eea9007dc8e4561b030eaea1772590`, and studio implementation
`c61569b8467ae279d262506039cecc57cbcbaca4` / tip `fe996d8`.
Both complete histories are now preserved by local integration merge
`4e5d47113ccd2617d896d85f0ace4eef78c948fd`; neither lane branch changed.
Prompt 8's actual handoff says partial/integration-blocked, not fully live.

## Code-path audit and smallest changes

| Blocker | Current code path / exact interface | Smallest central change | Consumers | Migration? / compatibility | Required checks |
|---|---|---|---|---|---|
| Network streaming | execution_api.complete → Gateway.stream → RuntimeInferencePort.stream; TargetAdapters.stream raises 503; runtime.guarded_request buffers a dictionary. Frozen stream can't carry actual cost or served identity and HTTP commits before preflight. | Shared approved-endpoint guarded async HTTP stream; typed upstream frames and terminal observation; prefetch before HTTP commitment; cancellation closure; reuse Gateway attempt/accounting logic. | Ports, adapters, gateway, HTTP, canonical generated clients | Additive event types; no existing row rewrite. Existing nonstream stays intact. | TCP/UTF8 splits, multi-frame chunks, keepalive/error/truncation, tools, terminal usage, cancellation/deadline, no fallback after delta |
| Tool / JSON support | ChatMessage roles exclude tool; request extra=forbid rejects tools/tool_choice/response_format; response/delta omit calls; choices requires nonempty. | Canonical tool definitions/calls/deltas, validated bounded JSON Schema subset and response formats, usage-only chunks; nonstream strict validation; reject unsupported combinations before transport. | Contracts/OpenAPI/TS, preflight, adapters, HTTP | Additive optional fields; old text requests unchanged. No table migration. | Request/output/tool-history validation; parameter mismatch; schema validation/refusal; unknown field errors; no tool execution in chat |
| Policy variants | ExecutableStage.configuration_id is primary, policy.version/transition and alias already immutable; no fallback pins or stage request restrictions; Selector has no calibrated quality mode. | Add bounded fallback IDs and route restrictions, explicit heuristic variant metadata; compile new draft versions only; check every fallback against same admission, key and aggregate budget. Never synthesize accuracy/quality. | Policy/admission validators, storage, selector composition, preflight, aliases/UI | Additive defaults; preserve original content digest rules for already persisted 2.0 records. No repinning or activation. | Old pins/digests, unknown hard gates, variant draft state, primary/fallback candidate scope and before/after commitment behavior |
| Second provider | ProviderCredentialReference only openrouter/local_ollama; TargetConfiguration deployment has no admin OpenAI-compatible endpoint. local_request fixes Ollama loopback. | Central admin Endpoint registration + approved configuration binding; fixed host/path/IP policy, no redirects or arbitrary client URLs; same typed OpenAI transport used by both. | Registry, config, provider adapters, preflight, generated contracts | Additive provider kind/endpoint reference; immutable metadata storage reused. | Endpoint/DNS/local-target restrictions, credential ownership, second-adapter actual loopback HTTP fixture, no live claim from compatible interface |
| Product / worker | create_app defaults execution_services=None; worker.run_once only planning; runner.submit executes inline; ComparisonPort uninstalled; no key product routes or attempt reads. Studio already calls canonical run/compare/activity APIs. | Central composition installs real ports against durable server records; explicit disabled/live runtime setting, no auto fixture provider. Persist queued inputs with expiry + execution context; worker claims once then reuses existing runner; comparison orchestrates same runs; studio key/status/attempt routes, generated client/UI consumption. | Settings, composition, API/auth, worker, execution storage, Prompt 8 UI | Forward migration for durable runtime queue/lease; old planning and runtime data preserved. Existing planning worker remains. | Product auth→key/alias→adapter→trace/accounting; worker queue, duplicates/restart, tenant isolation, workflows/comparisons, UI real state |

## Boundaries and sequencing

1. Change canonical shared types/interfaces on this branch; generate types once
   consumers are updated. No lane-private schema or unvalidated dict bypass.
2. Extend existing runtime code, reuse its verifier/authority/reservations/runner.
   Preserve zero automatic same-provider retries; only explicit bounded fallbacks
   before response commitment, within original caps. Failed attempts remain charged
   or uncertain. Strict JSON is validate-before-delivery, not claimed token streaming.
3. Compose server-owned approved registry, worker and studio. No HTTP grant creation.
   Synthetic provider output is only an explicit test fixture, never operational
   admission. Browser checks use a separate local test database and visible labels.
4. Run runtime/backend/frontend/lint/types/drift/build/migration/browser checks.
   Inspect only named existing configuration and credential presence (never values)
   after fixtures pass. Live target tests need scoped grants, exact endpoint/model,
   independent key, approved data class and cap. Otherwise report exactly
   `LIVE INFERENCE NOT VERIFIED`; second provider remains live-unverified.

Additional audited defects to resolve while extending: stream final-content/usage
reconciliation, volatile runtime composition, request/attempt read association,
app-key issuance atomicity, worker recovery without upstream redispatch, and
Prompt 8's activity refresh of persisted outputs. Existing npm development advisory
is centrally owned; do not hide audit output or sacrifice generated-contract checks.

No production merge, remote push, public deployment, tool side effects, purchases,
model downloads or assumed provider credits. Exact completion results will be in
`07b-runtime-complete.md`, not inferred from this plan.
