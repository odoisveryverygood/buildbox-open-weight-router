# Frozen foundation interfaces · v1.0

## Sandbox upgrade 2.0 — additive, not a v1 activation flag

`router/backend/buildbox_router/execution_contracts.py` composes existing Workflow,
CandidateConfiguration, Fact and EndpointRecord. It does not duplicate them or
change v1 DraftPolicy. `execution_ports.py` is the frozen lane boundary;
`execution_security.py` and `execution_storage.py` are shared guards/transactions.
`execution_api.py` declares working studio persistence and fail-closed future
execution endpoints. Runtime dispatch is deliberately not installed in milestone 06.

Migration 3 preserves existing records/jobs/provider calls, adding tenant-local
immutable sandbox records, CAS transition heads, budget reservations, application
key verifier storage and separately expiring private payloads. Aliases cannot be
repinned; a new policy version stays draft and never changes existing aliases.

Generated OpenAPI (including contract-only SSE/event/trace types) and TypeScript
come from `openapi_schema.py`. Python is pinned to 3.12 for repeatable generation.
The synthetic cross-lane policy fixture is `router/contract-fixtures/sandbox-policy-v2.json`.
See `upgrades/router-v2.md` for wire semantics, identity, admission, retention,
streaming, cancellation, idempotency and operational permissions.

## Integration planning API 1.1

`router/backend/buildbox_router/planning_contracts.py` composes the canonical v1
workflow/catalog records with exact plan versions, processing permissions, typed
target requirements, preserved clarification answers, immutable inputs and a
saved research/selection result. New endpoints are `/api/plans` and
`/api/plans/{id}/versions/{version}` with `/revise`, `/cancel` and `/policy` actions.
Job submission requires an owner-scoped idempotency key. Old recommendations
are not repinned; changed constraints create a new version and old exports fail.

Rich research records were promoted to `evidence_contracts.py`. The former
`research/records.py` contains compatibility re-exports, not duplicate schemas.
The v1 `Evidence` shape remains intact. Job records now include operation, phase,
progress, cancellation/uncertain states, budget accounting and actual served
control-plane metadata. Explicit migration revision 2 adds submission and provider
reservation tables. Generated OpenAPI/TypeScript remains the frontend authority.

`PlanningResult` is the persisted downstream boundary: exact `plan_id/version`,
validated interpretation/workflow, pinned catalog, optional rich `ResearchLedger`,
optional recommendation, exclusions, assumptions, missing facts, result status,
fixture marker and `evaluation_status=not_run`. A blocked result has no runnable
recommendation. No graph, policy or evidence object grants execution permission.

## Preserved foundation contracts

Canonical source: `router/backend/buildbox_router/contracts.py`.
Protocol source: `router/backend/buildbox_router/ports.py`.
Generated API description: `router/openapi.json`.
Generated frontend types: `router/web/src/generated/api.ts`.
Run `cd router && npm run generate`; do not edit generated schemas manually.

## Semantics

- All records carry `schema_version="1.0"`. Unknown facts have `value=null`, a
  nonempty `unknown_reason`, and provenance. Known zero/false are preserved.
- `ModelArtifact` describes weights/revision/license; `CandidateConfiguration`
  describes provider, region, quantization, hardware, harness, prompt and measured
  facts. Do not attach endpoint prices to the underlying model artifact.
- User-declared `WorkflowTool`, development `ResearchTool`, and connected
  `ExecutionTool` are separate types. No execution tool is enabled here.
- Outer workflow is a DAG with unique node/tool IDs. Bindings target named inputs
  or declared outputs of direct dependencies. Bounded agents must provide both
  iteration and model-call limits; no actual inner loop executes in foundation.
- Only `llm` and `bounded_agent` nodes receive model assignments. A policy compiler
  checks complete, unique coverage of precisely these nodes and their eligibility.
- Hard constraints fail closed on unknown values. Ranking presently uses synthetic
  cost only; it does not claim quality. Keep eligibility and ranking separate.
- Immutable database records are append-only. Pydantic frozen objects discourage
  reassignment but nested containers should still be treated as read-only; database
  triggers enforce durable immutability. New workflow content needs a new version.

## Lane ports

| Port | Input → output | Owner |
|---|---|---|
| Interpreter / Clarifier | Intake + assigned ID → Interpretation / material questions | Lane 2 |
| Selector | Workflow + CatalogSnapshot → FilterResult → ranked IDs → StackComparison / Recommendation | Lane 2 |
| PolicyCompiler | exact Workflow version + Recommendation → inactive DraftPolicy | Lane 2 |
| CatalogPort / ResearchPort | snapshot request / Workflow → CatalogSnapshot | Lane 3 |
| SearchPort | bounded query / public URL → source references / text | Integration transport; Lane 3 adapter implementation by approved scope |
| Evaluator | Recommendation + immutable holdout reference → EvaluationRun | Integration transport; future controlled evaluation |
| InferencePort | role + prompt → text | Integration owner |
| StoragePort | owner-scoped immutable objects + job lifecycle | Integration owner |

Composition injects adapters; lane implementations do not locate credentials or
construct clients on import. Research results cross the boundary as typed
snapshots, not sibling implementation objects.

## Jobs and API

Intake save → workflow version save → queued job. A separately started worker
claims queued/stale jobs using a compare-and-swap attempt token and a 60-second
lease, capped at three claims. Completed recommendation + snapshot + success status commit atomically.
Failures persist a sanitized typed error. A failed job requires new submission;
there is no automatic provider fallback or execution retry. Intake and workflow
saves are separate append-only writes: a crash before enqueue may leave a saved
intake/workflow without a job; resubmission is safe but not deduplicated.

The UI polls at one-second intervals for up to 60 seconds and preserves the job ID
in its URL. Evaluation is explicitly `not_run` with an unknown metric. Export is
idempotent and stores only allowlisted references; it never activates traffic.

Breaking changes require a version/migration proposal and integration-owner
approval before either lane modifies a shared file. Do not weaken validation to
make a fixture pass.
