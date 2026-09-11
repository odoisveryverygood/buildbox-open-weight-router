# Router v2 — actual validation report

September 10, 2026 (America/Los_Angeles). **Software/sandbox integration evidence;
no production reliability, model-quality improvement or market claim.**

## Execution boundary

Zero real target-provider requests and zero billable search requests were made.
Two synthetic configuration IDs use the SAME controlled loopback HTTP server.
OpenRouter request/stream behavior and native-local behavior are covered by
recorded/offline tests, not fresh vendor calls. The compatible HTTP adapter was
exercised over real loopback sockets. Fixed public packets came from retained
September 6 official metadata; runtime web search was not authorized or exercised.

## Acceptance results

| Scenario | Actual result | Remaining limit |
|---|---|---|
| A: research workflow | PARTIAL: UI activation → fixed public lookup → extraction → synthesis → three persisted outputs; two synthetic LLM attempts | Reviewed fixture graph, not arbitrary company research interpretation. No web search/read call or useful model-generated research answer validated. |
| B: structured comparison | LOCAL SOFTWARE PASS: identical two-sample set, two pinned configurations, four completed outputs; schema checks and expected-answer failures visible | Both configurations synthetic. Not a real two-model evaluation; initial test-policy sandbox admission precedes execution. |
| C: support tools | LOCAL SOFTWARE PASS: Python and TypeScript submit a simulated read-only lookup result with preserved `call-support-9` ID; undeclared/write tools rejected in contract/runtime tests | No business tool, real support model or upstream vendor tested. |
| D: client compatibility | PASS against actual local HTTP endpoint: Python 4 checks, TypeScript 4, cURL list 1; eight attempts, two tool-ID round trips | Explicit subset only. No universal OpenAI SDK compatibility claim. |
| E: versions | LOCAL SOFTWARE PASS: medium→small explicit edit creates `compare-b@2`; old admission gets 403; exact new admission enables it; old version/pin remains; reload persists | Synthetic operator admissions only. Rollback/CAS semantics additionally covered offline; no production traffic changed. |

The final browser run used the product `DeterministicSelector`, not the foundation
fixture selector. Its IDs were:

- Plan `ef47d90ca1914c6c80bb9ce301545c89@1`.
- Public packet run `5578d08d9ca64aaa888379471756760a`, policy `public-packet@1`.
- Comparison `dbde232546734d71ae0f8052536f86a5`.
- Policies `compare-a@1` → `fixture-small-local`; `compare-b@1` →
  `fixture-medium-local`; edited `compare-b@2` → `fixture-small-local`.
- Prompt revisions `compare-a-respond@1`, `compare-b-respond@1`; unchanged
  one-stage objective/template shape across the original two candidates.

These IDs persist in that temporary acceptance factory only. A restart creates a
new isolated fixture dataset, never mutates an old production result.

## Dataset, checks, timing and accounting

Dataset `browser_upgrade.js` synthetic receipt fixture v1 has **two** examples,
`Synthetic receipt 0/1`. User-declared holdout labels do not establish a clean
statistical holdout. Expected JSON is respectively `{"category":"ok"}` and
`{"category":"billing"}`. The strict schema requires only string `category`.
Both loopback configurations deliberately return `{"category":"ok"}` for both.

| Policy/sample | Schema | Reviewed exact match | Completion ms | Upstream ms | Pre-dispatch ms |
|---|---|---|---:|---:|---:|
| compare-a@1 / receipt 0 | pass | pass | 76 | 8 | 17 |
| compare-a@1 / receipt 1 | pass | fail | 33 | 3 | 5 |
| compare-b@1 / receipt 0 | pass | pass | 32 | 4 | 5 |
| compare-b@1 / receipt 1 | pass | fail | 50 | 8 | 11 |

There are four schema passes and two exact-match failures. This validates that
bad answers remain visible; it does not establish semantic accuracy. Each cell
has one reconciled synthetic attempt and fixture-declared $0 cost. Missing actual
costs elsewhere remain unknown. First content was not observed for nonstream runs.
Completion includes local queue/worker time; upstream is adapter wall time;
pre-dispatch is only part of gateway overhead, excluding initial HTTP/auth/selection
and finalization. No throughput, statistical latency or savings conclusion follows
from these four timings. The public-packet run adds two attempts: six total in the
browser workspace. The separate client harness has eight in its own workspace.

The public packet preserves `hub-1` URL, JSON locator, capture date, exact Qwen
repository/revision and declared license from retained official metadata. The
packet's generated synthetic `category` output is NOT a successful research answer.
The fixed-source two-LLM graph tests dependent-stage plumbing; the optimizer was
not forced to choose multiple models or represented as recommending them.

## Checks executed

- Verified upgrade base: `make check` — 296 tests. Runtime merge — 346. Studio
  merge — 355. Preserved later central 7B integration — 399. Each included its
  lint/type/build/generated-contract checks; merges occurred one at a time.
- Final `make check`: backend suite, Ruff/format, mypy, ESLint, TypeScript,
  Vite build and OpenAPI/TypeScript/synthetic-fixture generation drift checks.
  Exact final result is recorded in handoff 09 after the final run.
- `node web/tests/unit.cjs`: 14 checks passed.
- `uv run python -m tests.gateway.client_smoke`: 9 real-local-HTTP client checks
  passed; eight synthetic upstream attempts, zero external requests.
- `tests.gateway.pg_smoke`: PASS on empty UTF-8 local PostgreSQL database,
  migrations through v4, actual HTTP key auth/queue/worker/checkpoints/ownership.
- `scripts/check_upgrade_postgres.py`: PASS on separate empty UTF-8 database,
  v2→v4, rerun, legacy preservation, immutable records, tenant scope, CAS disable
  and atomic concurrent budget. Both databases report revisions 1,2,3,4.
- Playwright actual browser: acceptance passed, reload, four returned outputs,
  key create/hide/revoke and 390px activity/1440px comparison had no horizontal
  overflow. Final console inspection reported zero errors/warnings. Expected
  stale-admission HTTP 403 was asserted, not concealed. Actual video recorded.
- `npm audit --omit=optional`: zero vulnerabilities after the transitive lockfile
  update. Advisory reviewed: [GHSA-2883-xcg3-v3hh](https://github.com/advisories/GHSA-2883-xcg3-v3hh).
- `git diff --check`: passed. Built frontend scan for provider-key/private-key
  patterns and the synthetic Basic password returned no matching files. This
  bounded pattern scan is not a comprehensive independent secret/security audit.

## Failure/security coverage and honest failures

Existing suites plus `tests/gateway/test_upgrade_integration.py` exercise:
key expiry/revocation/scopes and tenant boundaries; draft/admission/version
isolation; malformed/oversized/inert imports; unknown capabilities/prices;
private/local-only processing gates; redirect/private-destination denial; injected
source text; pre-commit fallback versus mid-stream partial failure; no mixed-model
answer; bounded attempts/timeouts/cancellation with held unknown usage; atomic
concurrent caps; durable idempotency/checkpoints/expired leases without replay.
New checks cover current registry/packet revocation, content-pinned selection
caching, modality/tool distinction, retained source outputs, and shared selector
composition. Failures were injected through controlled transports, not vendors.

During development, the initial public packet exceeded the tiny synthetic 1,024
input-token envelope and stopped before inference. The explicit test fixture was
revised to 2,048 within its endpoint bound; guards were not removed. The initial
temporary PostgreSQL setup used SQL_ASCII and failed driver initialization;
separate UTF-8 databases passed. A selector-cache test initially used the legacy
fixture selector; inspection exposed and fixed the product composition mismatch.
An interrupted post-dispatch run remains conservatively uncertain; tests were not
weakened to claim it succeeded. These failed attempts are not live-provider failures.

## Not run / not established

Real eligible-model comparison, live OpenRouter, second real upstream, authorized
runtime web tools, managed secret onboarding, managed database and protected
preview are NOT RUN. No exact runtime grant/credential/spend/deployment approval
was available. General NL multi-tool interpretation, human-pause resumption,
free-form semantic rubric execution and full request/first-content latency need
additional implementation/validation. No production-readiness claim is made.
