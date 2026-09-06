# Lane B / Lane 3 research handoff — September 6, 2026

**Offline lane implementation: complete and tested.**
**Live runtime research: unavailable pending shared transport and authorization.**
**Model-quality validation: not performed.**

## Branch, worktree and foundation

- Branch: `codex/router-research`.
- Worktree: `/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-Research`.
- Exact base: `b36437fc91b717b3978f977ec3cdf084c8206a5b`.
- Tested implementation commit: `a212267ce53d6eb59e80ecf39578960669434c46`.
- This handoff is delivered in a following documentation-only commit. Resolve that
  commit with `git log -1 --format=%H -- docs/handoffs/03-research.md`; the tested
  implementation commit above contains every code/test/public-fixture change.

The branch was created with `git worktree add -b codex/router-research` from the
exact foundation commit. The merge base with `codex/router-intelligence` was
verified as that same commit. Lane A was not modified or merged. The original
internship checkout and its unrelated research/deliverables were not staged.

Before implementation, the lane read `AGENTS.md`, `docs/requirements.md`,
`docs/contracts.md`, `docs/TOOLS.md`, `docs/parallel-plan.md`, and
`docs/handoffs/01-foundation.md`, then inspected the canonical contracts, ports,
offline adapters, storage and research fixture. No additional standalone catalog
or security design files existed in the foundation document inventory.

## Delivered behavior

- Three typed, versioned roles: artifact discovery, capability evidence, deployment
  evidence. Exact artifact identities are fixed first; the two independent roles
  then run concurrently. Deterministic parsing needs no model assistance or prompts.
- Public publisher/repository/revision identity is separate from hosted endpoint
  identity. License/access unknowns and provider opacity are preserved.
- Rich lane-private evidence composes the frozen `ModelArtifact`, `Evidence`, and
  `Fact` types, with subjects, locators, source digests, observation/expiry dates,
  raw metrics/units, benchmark/method context and explicit limitations.
- Deterministic publication revalidates proposals against captured sources and
  reviewed table locators. Unknowns/conflicts remain explicit; no ranking or
  model-quality scores are invented or averaged.
- Cached fresh evidence is reused. Only relevant missing/expired roles revisit
  captured sources; replay does not reset timestamps. New snapshots are immutable
  and content-addressed. `SnapshotCatalog` pins a selected snapshot for a later
  recommendation rather than consulting a changing head.
- Calls, tokens, retries, timeouts, cancellation, response sizes and search-result
  limits are bounded. All roles share a locked spending/call reservation ledger
  within a run. The default budget is zero model tokens and zero dollars.
- Source prose cannot call a tool, raise a budget, publish an unvalidated record,
  change selection, connect business tools or activate routing. No workflow text
  enters search, extraction, logs, or public evidence.

## Actual public coverage

The successful offline replay produced:

`catalog-a2be51094b6a23d73f389cff636dc9e990dddd6c`

| Coverage | Count / meaning |
|---|---|
| Exact publisher releases | 8; all with observed 40-character repository revisions |
| Weight access | 6 public listings, 2 gated declarations; no weights downloaded |
| Retained public sources | 17 minimal metadata/excerpt records |
| Validated evidence annotations | 32: 9 identity, 8 license, 8 access, 5 capability, 1 deployment, 1 pricing |
| Publisher benchmark observations | 5 exact table cells; no tests run by Buildbox |
| Provider endpoint declarations | 1 Alibaba endpoint for Qwen3-8B |
| Canonical selectable configurations | 0; no real prompt/harness bindings were supplied |
| Overall evidence coverage | Partial; unavailable/missing evidence remains Unknown |

Releases: Qwen3-8B, Qwen3-Embedding-0.6B, Qwen2.5-VL-7B-Instruct,
Gemma-3-4b-it, Llama-3.1-8B-Instruct, Mistral-Small-3.1-24B-Instruct-2503,
Phi-4-mini-instruct, and DeepSeek-R1-Distill-Qwen-7B. The exact repository names,
revisions, source URLs and request outcomes are in
`router/tests/research/public/README.md` and the retained JSON captures.

Gemma/Llama pinned README requests returned 401; no access request or credential
retry followed. The selected Qwen2.5-VL OpenRouter endpoint path returned 404.
DeepSeek 7B returned an empty endpoint list. Neither outcome proves absence of
eligible models/endpoints. Three artifacts lack a parsed benchmark observation;
seven lack a matched endpoint declaration. Exhaustive modalities, true release
dates, benchmark test dates/sample sizes, and unreported serving facts remain
Unknown. License metadata is not independently reviewed or accepted legal terms.

## Adapter readiness and exact live boundary

`RecordedSources` is a working offline `SearchPort` adapter. Public-source
normalizers implement Hugging Face model metadata and OpenRouter model/endpoint
response parsing. `PublicResearch`/`SnapshotCatalog` satisfy the frozen research/
catalog boundaries. They are not wired into shared composition by this lane.

The bounded development capture used unauthenticated official HTTP reads only.
Eight Hugging Face metadata reads, six accessible pinned README captures, the
OpenRouter exact repository mapping and endpoint reads worked. One initial
metadata probe, inaccessible requests and documentation-read failures are listed
in the public audit; none is represented as successful evidence.

Bright Data search/extraction/status tools and Exa search were discovered in the
actual Codex tool inventory. No billable search, extraction or inference was
authorized or attempted; balances and runtime keys/zones were not assumed.
No Codex connector/session credential was copied into the application.

`RuntimePublicSearch` is explicitly fail-closed, not a disguised live adapter.
The missing shared fetch transport must enforce DNS/IP/TLS/redirect checks at
connection boundaries, deadlines/cancellation, typed transport outcomes and
approved runtime authentication. The tests verify refusal/lookup safety, not an
implemented live DNS/rebinding/redirect guard. Cross-process spending and hard
runtime cancellation remain unverified. The source-specific parsing and fixture
tests can be integrated once the owner delivers those shared capabilities.

## Executed validation

Commands ran in this worktree's `router/`, with isolated `.venv`, cache and local DB.

| Command/check | Actual result |
|---|---|
| `UV_CACHE_DIR=.local/cache-lane3 make setup` | Frozen Python setup and npm clean install succeeded; npm reported 0 vulnerabilities |
| `uv sync --frozen --python /opt/homebrew/opt/python@3.12/bin/python3.12` with lane cache | Recreated only this worktree's environment with foundation-compatible Python 3.12.13 |
| `UV_CACHE_DIR=.local/cache-lane3 make generate` | OpenAPI/TypeScript generation succeeded; final files match foundation byte-for-byte |
| `UV_CACHE_DIR=.local/cache-lane3 make check` | Ruff, formatting, ESLint, mypy, TypeScript, pytest, Vite build and generation drift checks passed |
| Full pytest within final `make check` | **119 passed**, two existing upstream deprecation warnings |
| `UV_CACHE_DIR=.local/cache-lane3 make test-research` | **86 passed** independently |
| Offline public replay command below | Succeeded; 8 artifacts / 32 claims / 1 endpoint / 0 bound configurations |
| `git diff --exit-code <base> -- <shared files / Lane A>` | No differences in contracts, ports, API, composition, storage, transports, manifests, generated files or Lane A |
| `git diff --cached --check` | Passed before implementation commit |
| Credential-pattern scan of lane files | No matching key/private-key/Bearer-token patterns |

The first default environment selected Python 3.13.15, whose HTTP 422 description
generated `Unprocessable Content` instead of the foundation's `Unprocessable Entity`.
Switching this worktree to the foundation's Python 3.12 and regenerating restored
the exact shared artifacts. No generated diff is committed. Initial implementation
type/test issues were corrected and final checks rerun. The integration owner
should consider a shared Python-version pin for reproducible generation; the lane
did not edit the manifest or root runtime instructions.

Tests cover identity/revision mapping, license/access unknowns, component price
conversion, missing/empty parameters, provider restrictions, exact benchmark
subjects, conflicts, freshness, immutable durable snapshots, cache-only reads,
selective price refresh, forged proposals, injected instructions, unsafe source
references, runtime refusal, response/search caps, timeout, cancellation, retry
caps, concurrent budget reservations, concurrent independent jobs and private-data
exclusion. Ordinary tests deny sockets through the foundation fixture.

```sh
UV_CACHE_DIR=.local/cache-lane3 uv run python -m buildbox_router.research \
  --sources tests/research/public/sources-2026-09-06.json \
  --plan tests/research/public/plan-2026-09-06.json \
  --database .local/lane3.db --output .local/lane3-public-replay
```

The local database and generated JSON outputs are ignored artifacts in this
worktree. No shared database, cloud resource, provider inference, customer tool,
deployment, routing activation, production write or remote push occurred.

## Files changed

- `router/backend/buildbox_router/research/`: new `records.py`, `evidence.py`,
  `normalizers.py`, `sources.py`, `bounds.py`, `jobs.py`, `catalog.py`, `service.py`,
  `__main__.py`, `README.md`. Existing `fixture.py` and `__init__.py` are unchanged.
- `router/tests/research/`: new `conftest.py`, `test_normalizers.py`,
  `test_jobs_and_catalog.py`, `test_security_and_bounds.py`,
  `test_shared_contract_requests.py`, plus `public/README.md`,
  `public/plan-2026-09-06.json`, `public/sources-2026-09-06.json`.
- `docs/change-requests/lane-3/01-evidence-and-configuration.md`.
- `docs/change-requests/lane-3/02-protected-runtime-research.md`.
- `docs/handoffs/03-research.md` (this documentation-only handoff).

## Shared requests and integration next steps

1. Review `01-evidence-and-configuration.md`: promote agreed rich fields through
   canonical shared versioning, preserve v1 unknowns, and supply real prompt/
   harness bindings. The executable blocker test proves v1 rejects the new fields.
2. Review `02-protected-runtime-research.md`: supply guarded fetch/inference ports,
   typed outcomes, independent runtime authorization and durable budget controls.
3. Decide how the rich ledger is exposed and committed with catalog snapshots.
   The frozen storage port currently permits an orphan ledger if a crash occurs
   between ledger-first and catalog writes; it never publishes a catalog first.
4. Compose the approved adapter centrally, then coordinate eligibility/selection
   with Lane A. Public endpoint declarations must not be treated as tested,
   license-cleared or exactly reproducible configurations.

No shared change request has been silently implemented. Shared/live modes still
fail closed; foundation UI/composition still use the original synthetic fixture.
