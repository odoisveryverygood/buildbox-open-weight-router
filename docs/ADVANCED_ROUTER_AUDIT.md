# Advanced router audit

Baseline inspected: `codex/router-v2-integration`,
`7bff0878d68921a11b6b35e238f8b6d1d66eddce`. September 13, 2026.
Production-shaped means implemented with safety/persistence boundaries; it does
not mean production-certified or live-provider verified. Paths below start at
`router/backend/buildbox_router/` unless otherwise noted.

| Existing capability | Location | Maturity | Actual limitation | Planned improvement |
|---|---|---|---|---|
| Task intake and clarification | `planning.py`, `workflow_proposal.py`, `intelligence/workflow/` | production-shaped | Local template/authorized interpreter; no rich normalized workload profile | Evidence-retaining deterministic analysis and explicit overrides |
| Artifact versus deployment identity | `contracts.py`, `evidence_contracts.py`, `runtime_catalog.py` | production-shaped | Eight retained public artifacts; no authorized live targets; sparse selection facts | Add normalized, dated deployment facts without replacing identities |
| Public research and evidence | `research/`, `evidence_contracts.py` | production-shaped | Bounded metadata jobs; benchmark claims not used in task-scoped utility | Typed reviewed performance evidence, retain conflicts and task scope |
| Candidate filtering | `intelligence/selection/engine.py` | production-shaped | Mostly workflow-wide region/price/modality/parameter gates | Stage-specific capability, context, privacy and total-budget checks |
| Ranking/portfolio search | same directory | demo-only | Ordinal price ranks plus complexity penalty; no evidence-based quality or Pareto | Normalized utility, unknown penalties, Pareto alternatives and confidence |
| Executable plans and version isolation | `execution_contracts.py`, `execution_policy.py`, `execution_storage.py` | production-shaped | Typed DAG/pins already exist; automatic stage-specific strategy selection missing | Compile new planning decisions into the same policies, not a second runner |
| Runtime and streaming | `gateway/service.py`, `gateway/adapters.py`, `stream_validation.py` | production-shaped | Real HTTP/SSE tested against synthetic transports; native local subset narrower | Preserve transports and response-commit boundaries |
| Workflow dependency frontiers | `gateway/runner.py`, `execution_jobs.py`, `worker.py` | production-shaped | Parallel waves/checkpoints already work; no quality-triggered escalation | Reuse DAG and capped gateway attempts; add modular validators |
| Tools/structured output | `gateway/runner.py`, `json_contracts.py` | production-shaped | Read-only registered packets; strict JSON separate from tool history; no arbitrary code | Deterministic completeness/syntax/citation checks; no business-tool expansion |
| Fallback | `gateway/service.py`, `gateway/preflight.py` | production-shaped | Pinned pre-delivery alternatives, bounded attempts; failure classification coarse | Policy-driven validation escalation and deployment circuit state |
| Provider health | no existing stateful circuit implementation | missing | No target-scoped recent-health feedback | Persist bounded health observations/circuit state; never global model bans |
| Accounting/security | `execution_storage.py`, `execution_security.py`, `gateway/keys.py`, `runtime.py` | production-shaped | Conservative budgets, private payloads, scoped keys, guarded egress; no live billing validation | Reuse all boundaries, add route-level aggregates without claiming billing completeness |
| Comparisons/evaluation | `execution_comparisons.py`, `sample_checks.py`, tests | production-shaped | Same-sample outputs/schema/exact match; no router-policy evaluation suite | Decision-only A/B/shadow reports, separate synthetic behavior from model quality |
| Frontend | `router/web/src/PlanningApp.tsx`, `studio/`, `DemoStudio.tsx` | production-shaped | Working studio; A–C demo uses explicit synthetic shortcuts | Add workload/profile/plan/what-if inspection using canonical generated contracts |
| API/persistence/migrations | `api.py`, `execution_api.py`, `migrations/` | production-shaped | Existing v4 append-only records and expiring payloads sufficient for additive records | Extend current API/storage; preserve digests and all old records |

## Implementation boundaries

No public research, paid calls, model downloads, account operations or deployment
is needed. All new demonstration performance data must be explicitly synthetic.
Public metadata never establishes accuracy. No executable arbitrary-code validator
or autonomous tool side effects. Runtime admissions, current privacy/capability
checks and aggregate reservations remain authoritative even after optimization.
No normal inference request may launch research or shadow inference.

The existing stakeholder demo stays intact. The new intelligence path must produce
the same canonical executable policy consumed by the existing worker/API; preview,
what-if and shadow decisions are not activation authority. Unknown hard requirements
block; unknown optional performance reduces confidence rather than becoming zero.
