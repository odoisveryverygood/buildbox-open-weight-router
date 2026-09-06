# Lane A / Lane 2 intelligence handoff

## Identity and scope

Base: `b36437fc91b717b3978f977ec3cdf084c8206a5b` (completed Prompt 1 foundation).
Branch: `codex/router-intelligence`.
Worktree: `Buildbox-Router-Intelligence`, created separately from the foundation.
The final delivery message records the exact lane commit; resolve the commit
containing this handoff with `git log -1 --format=%H -- docs/handoffs/02-intelligence.md`.

**Status: offline lane implementation delivered; full requested feature coverage
is PARTIAL because the frozen v1 contract cannot express several requirements.**
No shared file, other worktree, research/catalog implementation, schema, migration,
API/composition, generated type, lockfile, UI or deployment file was edited.
There is no Lane B integration, merge, push, deployed service or active policy.

The foundation's actual ownership mapping is `intelligence/**`, not top-level
`workflow/` and `selection/`. New modules are nested as:

- `router/backend/buildbox_router/intelligence/workflow/{clarification,interpreter,versions}.py`
- `router/backend/buildbox_router/intelligence/selection/{engine,estimates,policy}.py`
- Their package `__init__.py` files and `router/tests/intelligence/` tests/fixtures.
- This handoff only. Existing fixture implementations remain unchanged so the
  read-only foundation composition continues to behave as before.

## Implemented behavior

### Workflow interpretation and clarification

`SchemaInterpreter` implements the existing `Interpreter` port. It accepts
arbitrary description strings and validates injected recorded responses against
the canonical `Workflow` JSON Schema. This is **schema-constrained replay-tested
orchestration**, not a demonstrated live natural-language model or guaranteed
semantic extraction of all arbitrary descriptions.

A narrow, explicit local grammar also handles trim/lowercase/uppercase/sort-line/
deduplicate-line transformations without any model. It does not claim arbitrary
text understanding. Workflow content remains descriptive and is never executed.

Validation preserves caller identity, hard constraints, declared tool definitions,
required human review, no-model instructions, graph bindings, and explicit agent
bounds. The workflow is labeled `inference`, not falsely all user-stated. Logical
nodes are not interpreted as actual model/tool call counts. Outer graphs remain
acyclic; numeric loop caps must be explicitly stated and termination must be
mentioned. A typed termination predicate cannot be stored in v1 (request A3).

Repairs are capped at 0–2, default one. Refusal returns canonical `unsupported`;
unsupported schemas, malformed/truncated JSON, oversized output, unavailable
recordings and timeouts are mapped to existing `DomainError`/`ErrorCode` values
without echoing response/exception secrets. Synchronous port timeouts can only be
handled when the adapter raises them; transport-enforced deadlines need A2.

**Egress:** the foundation allows no external inference. Only an exact
`RecordedInference` instance (in-memory strings/exceptions, no client) is invoked.
Other injected `InferencePort` implementations are rejected before intake text is
passed to them. A declaration in intake text cannot authorize hosted processing.
No hosted fallback, credentials, paid/live calls or second inference client exist.
Live parsing and all external adapters are **UNTESTED / DISABLED**.

`ImpactClarifier` implements `Clarifier`. Versioned deterministic priority rules
focus first on conflicting hard restrictions, missing tool declarations, loop
bounds/termination and budget quantities, then missing objective/input/output or
requested quality criteria. Initial questions are capped at three;
`blockers(intake)` retains the full recomputable set. Each question explains the
eligibility/architecture/evaluation effect. This is a heuristic, not calibrated
information gain. Existing canonical constraint/tool answers are reused without
re-asking; richer persisted answer histories require A1/A3. The heuristic is not
a complete contradiction detector for arbitrary natural language.

`revise_workflow` creates the next canonical immutable version;
`persist_revision` verifies the exact owned prior version through `StoragePort`
and appends it. It never updates old jobs/recommendations or triggers execution.

### Selection, portfolios and estimates

`DeterministicSelector` implements `Selector`. Its public diagnostic helpers use
existing `Fact[bool]`: true=supported, false=contradicted, null=unknown, with rule
IDs and source IDs in ordinary canonical provenance. No parallel wire schema,
hidden capability field, or evidence-prose parser is introduced.

- Checks canonical open-weight status, known unit-price/latency ceilings and
  required region against evidence-linked artifact/configuration facts.
- Missing mandatory measurements/evidence never enter `eligible`.
  `needing_verification` and `rank_for_verification` show unknown-only candidates
  separately; `contradicted` reports established contradictions.
- Real catalogs are blocked pending exact downloadable-artifact/legal-policy
  fields. A model listing is not downloadable weights or legal suitability.
- Mandatory JSON/tool support, explicitly mentioned context/output/privacy/
  hardware/deployment/workflow-budget requirements are blocked when v1 cannot
  represent them. No hardware fit is derived from model size. This conservative
  phrase guard does not replace the missing typed requirements contract.
- Ranking `selection-1.0` uses evidence-linked known unit price before unknown,
  stable IDs, and a two-point ordinal penalty per extra configuration. Its score
  is neither expected accuracy nor dollars. No benchmark scores are averaged;
  unscoped evidence prose cannot change rankings.
- Bounded portfolio-first search explores one-, two-, and three-configuration
  mappings, with defaults of eight eligible candidates, eight model-using nodes,
  and 4,096 mappings. Unused configurations are removed. Ties are stable.
  Comparison prose reports distinct artifact/model count, configuration count,
  actual mappings examined, bounds and completeness. No global-optimality claim
  is made outside enumerated mappings. These counts lack typed v1 fields (A5).
- Since v1 has only uniform workflow-level capabilities/constraints, a single
  cheapest configuration often dominates; this is not a claim that heterogeneous
  stacks never help. Stage-specific evidence/compatibility needs A4/A5.
- Non-model stages receive no assignment. A purely deterministic workflow gets
  an empty model portfolio. Provisional recommendations say workload quality has
  not been established. Missing mandatory mappings raise a typed error rather
  than producing a complete-looking recommendation.
- Fallbacks are omitted and explained. The v1 policy has no fallback/retry
  semantics; the compiler refuses supplied alternatives rather than assuming
  they are safe fallback routes.

`token_component_cost` normalizes the existing per-1,000-token field using an
explicit canonical token-quantity Fact. Missing/invalid prices or quantities
return unknown, never zero. It is only a component calculation, not a total; the
currency is unspecified because v1 has no currency field, not assumed to be USD.
`projected_workflow_spend` returns unavailable because actual call/token/retry,
tool, provider-extra, and other quantities are absent. Recorded planning made no
paid inference/evaluation calls; that does not imply free customer workflow spend
or zero infrastructure cost. No savings figures were invented.

`SafeDraftCompiler` implements `PolicyCompiler` with an injected immutable copy of
the exact catalog. It rechecks workflow version/catalog, eligibility, complete
model-only mapping, portfolio bounds and fallback absence. It exports allowlisted
IDs and fixed explanations, not user/provider free text, endpoints or secrets.
Policies remain `draft`, `active=false`, `production_write=false`, with human
approval required. Old-version recommendations and incomplete mappings fail.

## Exact integration-owned contract requests (not implemented)

These are proposed canonical changes, **not existing fields**. All require
integration-owner approval, a contract version bump, regenerated frontend types
and storage/API migration decisions. No lane-local substitutes were added.

| Request | Exact proposed canonical change | Current consequence |
|---|---|---|
| A1: grounded intake and field provenance | Add `SourceSpan(document_id, revision, start, end, quote_hash)`; extend versioned provenance kinds with `user_stated`, `inferred`, `proposed_default`, `unknown`, preserving a migration from v1 labels. Add source-backed `objective`, typed input/output specs, `preferences`, `success_criteria`, and first-class `ClarificationAnswer(question_id, value, spans, supersedes)` on Intake/Workflow. | Cannot retain typed source spans, all requested provenance categories, complete extraction or durable general answer reuse. They are not embedded in `source` strings. |
| A2: egress and inference outcomes | Add integration-verified `ProcessingGrant(principal, intake_revision, purpose, allowed_adapter_ids, locality, expires_at)` and adapter registry locality. Replace raw inference text return with a versioned result carrying content/refusal/finish_reason; request includes response schema, timeout, token cap, repair budget and grant reference. | All non-recorded inference blocked; no safe live parsing, enforced timeout or reliable refusal/truncation distinction from a string-only port. Never derive consent by calling a hosted model. |
| A3: stages, tools and revisions | Add tool availability/request status separate from execution authorization; typed `termination_condition`, model/tool-call ranges with provenance; first-class revision/answer submission returning pinned workflow and immutable content hash. | Tool declarations are not verified availability; stop behavior is not a typed predicate; richer answer editing cannot be integrated without API changes. Existing version helper appends safely and leaves jobs pinned. |
| A4: artifact/config eligibility and scoped evaluation | Add artifact download verification for exact revision/checksum and `license_policy_id` evaluation; config effective input/context/output limits, modality, tool/structured-output support, deployment/region/privacy/retention facts and measured hardware requirements. Add `EvaluationEvidence(dataset_id/hash, split, workflow_version/hash, config_id/hash, metric_name/direction, value, sample_count, coverage, settings_hash, outcome_source)` and benchmark identity/version/settings/coverage. | Real-catalog admissibility, contextual legal fit, capability-aware stage assignment and workload-specific evaluation ranking cannot be implemented from v1 fields. Existing EvaluationRun lacks configuration/metric scope; evidence prose is not parsed as a surrogate. |
| A5: selection diagnostics and search | Add typed `EligibilityCheck(rule_id, status, fact_refs, reason_code)`, candidate admissible/contradicted/needs-verification buckets, per-node requirement references; add typed `PortfolioComparison(model_count, configuration_count, mappings_examined, search_bounds, complete, heuristic_version)` and provisional/blocked recommendation status. Extend compare port to take Workflow, snapshot and scoped eval evidence. | Canonical Facts provide tri-state checks, but FilterResult has only eligible/excluded. Comparison details are human-readable rationale, not machine-readable counts. No stage-specific optimizer benefit or typed provisional status can be fabricated. |
| A6: spend and safe fallback | Add scoped `UsageEstimate` facts for calls, input/output/reasoning tokens, retries, tools, extra components; price currency/unit/direction/timestamp; separate planning/evaluation/projected-workflow budgets and ranges. Add per-node fallback candidates with the same eligibility checks and explicit retry budget in draft policy. | Total hard-budget checks stay unavailable/blocked and fallbacks stay omitted. Existing blended unit price cannot establish actual workflow spend. |

## Tests and executed results

Commands executed from this worktree's `router/`, using the isolated
`UV_CACHE_DIR=.local/cache-lane2` and local `.venv`:

| Command/check | Actual result |
|---|---|
| `uv sync --frozen --python /opt/homebrew/opt/python@3.12/bin/python3.12` | Existing lockfile installed successfully; no manifest/lockfile changes or added dependencies |
| `uv run pytest tests/intelligence -q` | **105 passed**, including the seven untouched foundation lane tests |
| `uv run pytest -q` | **134 passed**, including the full foundation regression suite |
| `uv run ruff check backend/buildbox_router/intelligence tests/intelligence` | Passed |
| `uv run ruff format --check backend/buildbox_router/intelligence tests/intelligence` | Passed; 14 Python files formatted |
| `uv run mypy backend/buildbox_router/intelligence` | Passed; 10 implementation files |
| `uv run mypy` | Passed; 23 backend files including frozen shared code |
| `git diff --check` and protected-path comparison to base | Passed; shared/schema/API/UI/research/lockfile files unchanged |
| Secret-pattern scan of owned source/tests/handoff | No provider-key/private-key/personal-email matches |

Thirty explicit synthetic intake cases live in `tests/intelligence/intakes.json`:
extraction/classification, support/tool use, research, bounded agents, deterministic
transformations, ambiguous/conflicting requests and unsupported tasks. The model
responses are deliberately constructed recordings, not results of a live model
test. Additional tests cover refusal, timeout/unavailability, malformed/truncated
JSON, unsupported schema, bounded repairs, egress rejection before transmission,
unknown/invalid cost, source IDs, no invented tools/limits, hard constraint and
human-review preservation, answer reuse, all-blocker retention, immutable revision
and job pinning, tightened-filter monotonicity, fallback omission, safe exports,
no-model stages, deterministic replay and catalog permutations. Sixteen seeded
tiny cases compare the portfolio-first optimizer against an independently written
exhaustive assignment-product reference.

Initial tests caught a missing `accurately` clarification trigger and a false tool
request from negated `never send` text. Both implementations were corrected; the
tests were not weakened. The full suite retains the foundation's two upstream
Starlette/httpx/AnyIO deprecation warnings. No acceptance claim is made for live
parsing, unsupported contract fields, UI wiring or Lane B integration. Frontend
build/browser and live PostgreSQL were not rerun because those files/runtime are
outside this lane's scope; their earlier foundation status is not upgraded here.

## Integration instructions

1. Review A1–A6 before extending canonical contracts. Do not treat the conservative
   guards as a substitute for typed requirements.
2. Composition owner can inject `SchemaInterpreter(RecordedInference(...))`,
   `ImpactClarifier`, `DeterministicSelector`, and `SafeDraftCompiler(snapshot)`
   behind existing ports. These classes do not locate credentials on import.
3. Do not replace existing fixture UI behavior silently. Add explicit recorded
   interpretation/selection mode in integration-owned composition and tests.
4. Research data must arrive as `CatalogSnapshot`; there are no imports from the
   research implementation. No Lane B merge/integration has been performed.
5. Keep shared/live mode disabled until authenticated egress and real database,
   evaluation and deployment checks are approved and performed.
