# Open-weight workload intelligence

September 13, 2026. A sandbox implementation, not a production or model-quality certification.

## Product thesis

Give Buildbox a workload, not a model name. It derives inspectable requirements,
filters exact model/deployment configurations, exposes evidence and uncertainty,
and compiles a bounded execution strategy into the existing sandbox runtime.
Its differentiator is the **decision about what should run where and why**, not
another transport API. It does not claim to have discovered universally best models.

```text
Workload + explicit overrides
              │
       workload.py rules                 owned immutable catalog
              │                                  │
       WorkloadProfile ── policy / budgets / privacy
              │                                  │
       planner.py: bounded strategy              │
              │                                  │
       existing eligibility + stage hard gates ◄─┘
              │
       task evidence + deployment circuit + economics
              │
       normalized utility / Pareto / confidence
              │
       immutable RoutingDecision ── decision-only what-if / shadow
              │
       canonical ExecutablePolicy (DRAFT)
              │
       exact operator admission + explicit sandbox transition
              │
       existing worker / dependency waves / gateway
              │
       registered transport A or B; validated read-only tools
              │
       output validation / bounded pinned fallback or repair → revalidate
              │
       persisted outputs + every attempt + usage reconciliation
              │
       immutable outcome + optional explicit rating; no automatic quality promotion
```

Paths in the following sections are relative to `router/backend/buildbox_router/`.

## Reuse and boundaries

`contracts.py` remains the catalog/workflow authority. `execution_contracts.py`
remains the executable policy, alias, input-binding, budget and trace authority.
`routing_contracts.py` adds workload decision DTOs, not a second executable graph.
The new planner compiles into `ExecutablePolicy`; it does not dispatch models.
`gateway/runner.py`, `gateway/service.py`, adapters, imports, comparisons and keys
are the same components used by the original product. Generated OpenAPI and
TypeScript remain centralized. No dependencies or provider integrations were added.

### Model ≠ deployment ≠ authority

An existing `ModelArtifact` identifies weights/publisher/license. A
`CandidateConfiguration` identifies its serving configuration; runtime targets
bind that configuration to a separately approved endpoint/credential reference.
Several deployments can reference one artifact. Native local inference and
approved OpenAI-compatible endpoints already exist. The new capability map can
describe backend compatibility, quantization and hardware without asserting those
runtimes are connected. No vLLM/TGI/Ollama process, weights or GPU was installed.

Discovery is not eligibility; eligibility is not callability. Base weights/license
gates and current tenant/runtime admissions are retained. Local-only dispatch is
checked against the approved endpoint's **actual loopback network declaration**,
not the word "local" in a catalog name. Privacy/retention facts remain separate.

## Workload understanding

`intelligence/workload.py` uses bounded, inspectable rules for 15 task families,
modalities, structured output, privacy and decomposition/verification/parallel hints.
`WorkloadProfile` includes input/output envelopes, optional/required capabilities,
tools, sensitivities, determinism, strategy, cost/latency/call limits and field-level
rule/override evidence. Explicit supplied fields take precedence. Inconsistent
mandatory JSON/tool requirements cannot be removed by weakening the capability list.

Unknown token envelopes prompt clarification and block an executable preview.
Exact deterministic model output is unsupported, even at temperature zero.
The complete objective is retained in tenant-owned decision/prompt records; rule
evidence contains no copied private prose. Literal workload text cannot introduce
new template bindings. No analysis or inference request launches public research.

These are transparent keyword rules, not general language comprehension. Negation
and ambiguous prose require explicit correction. Sensitivity/preferred-cost fields
are descriptive; actual utility weights are explicit policy controls. Do not claim
that arbitrary prose has been perfectly interpreted.

## Capability ontology and evidence

`DeploymentIntelligence` attaches a typed capability map to the exact configuration:
input/output modalities, JSON/schema/tools/streaming, context/output limits,
architecture/family/size/quantization/backends, latency/throughput, component prices,
hardware, local/self-hosted status and retention/privacy. Missing keys mean unknown.
Every present `CapabilityObservation` includes `Fact`, provenance, evidence IDs,
basis, observation and expiry. Known false is distinct from unknown; numeric fields
cannot silently become booleans or non-finite values. Hard gates reject stale,
missing and merely estimated facts. Observation is not a measurement timestamp.

`PerformanceEvidence` retains exact configuration, task, benchmark/version/split,
harness/settings, raw metric/unit, explicit normalization scale/direction, sample
size, measurement/retrieval/expiry, source locator, review state and limitations.
Normalization is deterministically checked against the raw value. Only reviewed,
current, task-matching evidence can influence utility. Unlike methods across
configurations or conflicting scores remain unknown; they are not averaged.
Repeated identical evidence is not independent corroboration. Coding scores do not
rank summarization. Public metadata alone never establishes workload accuracy.

The retained public catalog/research pipeline is unchanged. **New task-performance
coverage is synthetic only.** No real benchmark scores were fabricated or fetched.
Operators must curate reviewed intelligence into new immutable catalog snapshots;
there is no untrusted HTTP endpoint for granting eligibility or uploading live facts.
Expiry is source/field-specific snapshot policy, not a universal freshness claim.

## Decision algorithm

`intelligence/optimization.py` performs:

1. Existing artifact/access/license/deployment filter.
2. Stage-specific capabilities, context/output envelopes, provider/privacy,
   determinism, tool restrictions and circuit gates.
3. Hard cost, latency and task-quality floors. A score cannot bypass a rejection.
4. Utility over configurable quality, latency, cost, throughput, privacy,
   reliability and optional-capability weights. Known values are min/max normalized
   across the eligible set; cost/latency directions are reversed. Weight totals are
   normalized. Unknown objectives receive a configurable negative penalty; estimates
   receive a discount. Unknown values are never silently zero measurements.
5. Pareto selection over active objectives. An unknown metric cannot dominate a
   known one. All candidates, rejections, metric bases and component scores persist.
6. Separate routing confidence from model-quality confidence. A sole hard-eligible
   deployment gives high confidence in constraint satisfaction relative to the
   pinned catalog. Close utilities give medium routing confidence; missing compatible
   objective evidence gives low; complete compatible objectives and a clear margin
   give high. Synthetic catalog scope is explicit. Model-quality confidence still
   requires measured task coverage/sample thresholds; synthetic quality remains LOW.
   The legacy `confidence` field retains quality semantics for old clients.

Cost forecast in micro-USD is `input_tokens × input_USD_per_million +
output_tokens × output_USD_per_million + request_USD × 1e6`. Per-attempt reservations
round upward. Prices without units or unknown components cannot create a ready
executable plan. Predictions are not actual billing or latency guarantees.

Explanations are rendered from the same decision rows: understood task, hard
requirements, rejected/eligible counts, exact selected ID, weighted objectives,
Pareto count, derived cost/latency deltas and confidence reasons. No explanation LLM
or invented percentage is used. Catalog IDs and content digests are frozen.

## Planning and execution

| Strategy | Actual behavior |
|---|---|
| Single | Default unless a supported expansion is requested/inferred. |
| Multi-stage | Extraction → task-specific reasoning → synthesis, independently selected per stage. |
| Parallel | Three bounded analysis/review branches → synthesis; existing dependency-wave runtime executes them. |
| Cheap-first | Cost-ordered primary; only eligible candidates with higher comparable task evidence may be escalation targets. Literal reviewed validation criteria are required. |
| Generate + verify | Generator → verifier. With explicit deterministic acceptance criteria and repairs enabled, the deterministic validator is the verifier; failed checks trigger bounded same-target repair and revalidation. Otherwise the existing separate LLM verifier remains. No independence or superior quality claim. |

All templates compile through `ExecutionPlan` (`dag-1`) into the same canonical
workflow and runtime. `/preview` also accepts a reviewed custom graph of up to eight
text stages, task families, dependencies, validators and bounded repair/escalation
edges. Input order is normalized topologically; cycles/missing dependencies and
duplicates are rejected. Independent stages run concurrently; dependent synthesis
receives the named predecessor results plus the original input. Validation is a
typed post-generation control step within each node, not another model call.
Only validated output crosses a dependency edge. No autonomous graph editing or
global search over arbitrary DAGs is claimed.
Planned worst-case calls include every allowed attempt. Cost is summed across
stages/attempts; latency follows the critical path rather than adding parallel
branches. Hard caps block impossible plans. Input envelopes must include prompt
and predecessor text; actual preflight checks can still reject an underestimated
envelope safely. General custom schemas/prompts remain editable in the full studio.

The new automatic compiler is text-only and does not invent registered business
tool graphs. Existing read-only tool workflows and tool-call IDs still work in the
full studio/API. Multimodal or unnamed/unapproved tool execution blocks, regardless
of catalog capability. No arbitrary code execution was introduced.

## Validation, adaptive execution and health

Existing JSON/schema/tool-result validators are preserved. `validators.py` adds
bounded literal completeness, Python syntax parsing (no execution) and exact
citation-URL allowlist checks (no fetch or entailment claim). A critic is not an
automatic quality oracle. Failed output validation remains visible and accounted.

`fallback_on` restricts allowable failure classes for pinned attempts. There are at
most three total attempts per node (original + fallbacks + repairs), no indefinite
retry, no fallback after response
commit, and no repeated business-tool side effects. Failed/partial requests retain
unknown charges as pending. Strict post-output validators reject streaming before
dispatch; they cannot retrospectively withdraw an invalid streamed answer.

`max_repairs` is configurable from zero to two, requires explicit validators and
reserved attempt capacity, and defaults to zero for compatibility. Only invalid
output/quality-validation failures can trigger repair. Repair uses the same pinned
target and prompt with the failed output/checks supplied as untrusted data; it
re-enters authorization, privacy, input-envelope, cost and deadline checks.
Tool-bearing repair is rejected. Invalid original outputs use private expiring
storage. Every attempt has its own output reference where invalid, validation,
recovery action/reason, usage reservation and final reconciliation. SSE usage
events include all settled attempts. Known-charge validation exhaustion is a failed
run, not an ambiguous provider charge; unknown charges remain uncertain.
Worst-case repair reservations include the full input envelope and round each
attempt upward separately, avoiding aggregate-rounding under-reservation.

Revision 5 adds `deployment_health`, scoped by tenant + configuration + catalog.
Transport failure/rate-limit/timeout observations can open a configurable circuit;
validation failures do not mark a provider unavailable. An atomic lease allows one
recovery probe after cooldown. Another deployment of the same artifact is not
globally disabled. Current circuits affect previews and are rechecked at dispatch.
Normal requests never send health-probe traffic separately. Synthetic health
scenarios are labeled; the counters are not production measurements.

Health currently gates availability rather than implementing a calibrated
time-decayed reliability model. Some adapter failures remain coarsely classified;
context-overflow and arbitrary tool-quality escalation are not fully automated.

## Versioning, simulation and accounting

Tenant-scoped router policies and decisions use existing append-only records.
Changing a policy with the same ID/version conflicts. What-if creates a separate
decision; shadow compares decisions only and never runs extra models. Old routes,
catalogs, outputs and admissions stay unchanged. An experimental draft needs a new
exact admission. Manual edits invalidate the automatic-winner attribution and
recheck advanced hard gates; historical versions retain their original decisions.

Each advanced attempt references router policy, catalog ID/digest, capability
schema, workflow/prompt/policy version, exact target and admission. Failed validation
and fallback reason join existing usage reconciliation. Historical admission digests
retain legacy serialization behavior; generated fixtures and tests verify it.

The metrics API provides bounded tenant-scoped decision distributions, confidence,
rejection reasons, attempt/fallback/failure rates, latency, known cost and unknown-cost
counts plus policy disagreement. It is not an unlimited analytics or billing export.
Detailed tool/schema outcomes remain in existing runs/attempts/comparison records;
dedicated aggregate tool/schema-rate dashboards are not added.

Terminal workflow executions append content-free `ExecutionOutcome` observations
with exact run/policy/catalog/decision references, status, final validation, earlier
failed checks, summed attempt latency (not parallel wall time), known cost,
unknown-charge count, fallback and repair usage. One optional immutable 1–5 user
rating can be attached through tenant-scoped studio authorization. Query coverage
is at most 1000 records; these observations never alter ranking or become benchmark
truth. Existing append-only storage and private output TTL are reused; no migration
or second evidence database is needed. Dedicated retention quotas remain future
production work rather than deletion of historical snapshots.

## API and UI

New authenticated `/api/studio/intelligence` endpoints:

| Method/path suffix | Behavior |
|---|---|
| GET `/status` | Owned catalog snapshots; explicitly injected D–K fixtures only in test composition |
| POST `/analyze` | Local `WorkloadProfile`, no persistence or inference |
| POST `/preview` | Saved immutable decision, no activation |
| GET `/decisions/{id}` | Tenant-owned complete decision |
| POST `/decisions/{id}/what-if` or `/shadow` | Recompute or compare policy decisions; no model calls |
| POST `/drafts` | Compile a saved ready decision into the canonical draft policy |
| POST `/catalog-diff` | Artifact/deployment/capability/price/evidence snapshot differences |
| POST `/evaluate` | Up to 30 saved decision comparisons; explicitly router behavior only |
| GET `/metrics` | Bounded recorded aggregates with unknowns retained |
| GET `/outcomes` | Tenant-scoped content-free terminal outcomes and explicit ratings; no ranking effect |
| POST `/outcomes/{run_id}/rating` | One immutable explicit rating for an owned outcome; identical repeats idempotent |

Execution, outputs, imports, comparison and aliases reuse the existing sandbox and
studio APIs. `/v1/models` and `/v1/chat/completions` remain the documented subset;
one chat completion does not execute a whole DAG. New UI: `/?intelligence=1`.
It shows the profile, stage dependencies, alternatives, evidence, what-if, exact
draft/admission and actual persisted stage outputs/usage. Stage checkpoints are not
pretend token streams. Original A–C streaming and full studio remain available.

## Evaluation and next engineering boundary

`tests/gateway/test_advanced_router.py` covers hard gates, unknown/stale facts,
normalization, cross-method conflicts, Pareto, explanation consistency, confidence,
strategy budgets, typed DAG execution, validators, escalation, circuits, immutable
versions, tenant access and no-authority what-if. Existing security/runtime tests
remain unchanged apart from forward migration/legacy-fixture expectations.

`test_sandbox_completion.py` adds repair pass/exhaustion/skip, preserved invalid
output and both charges/events, custom graph order/parallel fan-in, conditional
escalation, hard caps, immutable rating/tenant boundaries and confidence separation.
Scenario K in `/?intelligence=1` shows a synthetic invalid generation → one repair
→ passing validation, both outputs and attempts, and the recorded outcome.

`uv run python -m tests.gateway.evaluate_advanced --output output/advanced-evaluation.json`
creates an isolated loopback test composition. It compares two policies for nine
task families, executes eight authorized synthetic workflows, and expects the
unapproved-tool case to block. Reports retain profiles, ranks, versions, outputs,
attempts, timing and usage. Literal fixture integrity is not semantic model quality.
Live quality, production reliability and quality improvement are **not verified**.

Highest-leverage next milestone: collect a small reviewed outcome-linked holdout
suite and evaluate two approved real open-weight deployments against a pinned
single-model baseline, with explicit budgets. Calibrate workload rules, strategy
selection and uncertainty from that evidence before claiming better routing quality.
