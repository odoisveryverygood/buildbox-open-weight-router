# Buildbox stakeholder demo

Research-free demo-readiness pass · September 13, 2026 · local sandbox, not production.

## What this is

Buildbox turns workflow requirements into an inspectable model configuration and a versioned route. Users can inspect candidates, edit workflows, compare outputs, explicitly enable a sandbox version, and see every execution attempt. This presentation uses the real product pipeline with clearly simulated model responses and catalog facts.

## Start and reset

```sh
cd "/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-V2-Integration/router"
make demo
```

Open **http://127.0.0.1:5202/?demo=1**. If prompted, use the public, local **TEST** identity `fixture` / `synthetic-test-password` (not a provider key). Requires existing uv, Node/npm and local dependency downloads on first setup; no paid credentials. The command builds the UI, starts the API/worker and loopback simulator, and creates a fresh isolated database. It refuses occupied ports rather than terminating other work.

Keep the terminal running. Ctrl-C then `make demo` gives a clean reset; old temporary databases/audit data are retained. **Reset presentation** clears the displayed result only. Demo admissions and output retention last one hour; restart before presenting if the session is older. Optional `BUILDBOX_DEMO_API_PORT` / `BUILDBOX_DEMO_WEB_PORT` change the local ports together with the proxy. Logs are printed by the launcher.

## What is actually implemented

- Deterministic requirements filtering, cost ordering, explicit pins and inspectable exclusions.
- Canonical versioned policies, sandbox transitions, scoped application keys and exact aliases.
- Real API → queue/worker → guarded HTTP transport → persisted output and attempt accounting.
- Incremental SSE stage responses; completed stream results reload without another execution.
- Side-by-side comparison of the same sample on two exact policies, with visible validation results.
- Tool-call IDs/results, separate schema-validated JSON delivery, and pre-response fallback.
- Existing full studio: task entry, stage/prompt edits, version history, imports, routes and API examples.

## 5-minute demo

1. **0:00 — Open the product.** Read the one-line demo indicator. Choose **A · Everyday summary**. The task and requirements are shown; this shortcut uses preconfigured requirements, not live LLM interpretation.
2. **0:30 — Explain the decision.** Expand **Alternatives considered**. Small is the lowest-priced eligible fixture; region/cost exclusions come from actual selector checks. Latency and quality are not benchmarked.
3. **1:00 — Execute.** Click **Run workflow**; wait for `Workflow succeeded`. Click **Stream stage output** to show chunks arriving. These are two separately accounted actions using the same pinned stage/configuration, not a hidden DAG in the chat endpoint.
4. **1:40 — Compare.** Click **Compare alternate route**. Inspect the two returned outputs, exact-match checks and completion times. One synthetic sample per policy is not evidence of a quality winner.
5. **2:20 — Change the priority.** Choose **B · Complex review**. Inspect its explicit medium-model pin and eligible cheaper alternative; click **Run workflow**. Explain that the pin demonstrates user control, not a proved intelligence advantage. The full-studio link opens the actual plan/version for deeper editing after the main demo.
6. **3:00 — Show capabilities.** Choose **C · Tools + JSON**, then **Stream stage output**. Inspect `lookup_support` and `call-demo-shipping`; click **Approve read-only lookup**. Approval sends the simulated client-owned result with the original ID, then performs a separate strict-JSON call. Two extra attempts are intentionally disclosed; undeclared tools are not executed.
7. **4:00 — Show resilience.** Choose A again, then **Demonstrate safe fallback**. Inspect small → controlled pre-response 503 → allowed medium → final text. Both use the same simulator, not two independent providers.
8. **4:30 — Close with accountability.** Inspect **Results & accounting**: every attempt, synthetic tokens/costs, measured local duration and unknown failed-attempt usage. Reload, click **Load last saved result**, and confirm no new call. Explain the live prerequisites below.

## Three scenarios

| Scenario | What changes the route | What it proves |
|---|---|---|
| A: Everyday summary | Minimum supported catalog price after region/cost gates | Real filtering/order; no unmeasured speed claim |
| B: Complex review | Explicit reviewer pin to eligible medium fixture | Versioned configuration control; not superior intelligence |
| C: Tools + JSON | Declared tool and structured-output requirements | Capability filtering, tool-ID round trip and schema validation |

The supported fixture identities are `fixture-small-local`, `fixture-medium-local`, `fixture-over-budget`, and `fixture-other-region`. They are not verified public model releases. Do not rename them to real vendors or advertise their prices/capabilities as market facts.

## Architecture

```text
Task
 ↓
Requirements extraction / policy (demo shortcuts use explicit requirements)
 ↓
Candidate filtering
 ↓
Routing / scoring
 ↓
Selected worker / model configuration
 ↓
Runtime (HTTP to a loopback simulator in this demo)
 ↓
Streaming result
 ↓
Accounting + persisted run
```

Workflow runs use the queued worker. The separate Chat Completions subset calls one pinned stage; it never secretly executes the workflow. Both use canonical policies, configuration eligibility and attempt accounting.

## Demo vs live

**Real:** routing decisions from actual requirements/checks, version isolation, activation checks, authorization, HTTP/SSE transport, worker checkpoints, storage, comparison checks, and accounting aggregation. Browser/runtime durations are measured locally, including deliberate simulator pacing.

**Synthetic:** catalog evidence/prices/capabilities, model text and tool requests, shipping lookup data, expected answers, provider-reported tokens and zero successful cost. Failed-attempt usage can remain unknown. This is neither live inference verification nor a model-quality/latency benchmark. The high-intelligence example is an explicit pin, not a seeded performance ranking.

**Requires live access:** provider inference, real workload quality/cost measurements, and live research tools. A development connector does not supply deployed runtime credentials. Public-source packets in the existing studio are retained data, not live web searches.

## Production activation — external prerequisites

- Approved exact model/provider targets with current eligibility evidence and license/privacy decisions.
- Provider credentials via an approved server-side secret store, scoped operator admissions and explicit spending caps.
- Authorized read-only runtime research tools and budgets if live web workflows are required.
- Approved protected hosting target with authenticated backend/worker, database, TLS and retention requirements.

There is **no shareable deployment**. The smallest next step is to select and authorize a protected full-stack hosting target. The frontend proxy is environment-configurable (`ROUTER_API_ORIGIN`); production host/security configuration still requires review. Never deploy `tests.gateway.browser_fixture`, its public identity, or `make demo`; they are loopback-only acceptance tooling.

## Current artifacts and verification

Fresh screenshots and a real browser recording are under:
`/Users/aradhyamishra/Documents/ChatGPT/Buildbox-Router-V2-Integration/router/output/playwright/demo-artifacts/`

`01-main.png`, `02-routing.png`, `03-stream.png`, `04-comparison.png`, `05-tools-json.png`, `06-fallback.png`, `07-accounting.png`, `08-mobile.png`, `stakeholder-demo-current.webm`.

See `docs/handoffs/10-stakeholder-demo.md` for executed checks and limits. Media is local/ignored by Git; preserve that directory when sharing the recorded demo. The recording is automated browser interaction, not a narrated presentation.
