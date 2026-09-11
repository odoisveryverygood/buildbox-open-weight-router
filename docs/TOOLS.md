# Tool access and runtime boundary

## 7B integration refresh — September 8–9, 2026

This refresh supersedes availability statements below for this integration task;
older connector successes are historical, not rerun here.

| Access | Verified in this task | Runtime / authorization boundary |
|---|---|---|
| Local repository / Git | Integration worktree and both lane histories read; no remotes configured. Local merge preserves both lanes. | No push, production merge, public deployment or other-project edits. |
| Local Python / Node | Existing uv environment, Ruff, mypy, pytest, TypeScript, Vite and generated-schema tooling executed. | Tests do not discover credentials or construct live clients on import. |
| Playwright | Installed skill read; CLI actual browser on isolated 5199/8029 app; Prompt 8 regression and runtime flow exercised. | Explicit synthetic HTTP provider fixture and private temporary DB, not a second live provider. |
| PostgreSQL 17 | Native Homebrew toolchain; isolated loopback 55439 UTF-8 databases; migration and API/worker/accounting checks. | No cloud database provisioned or production DB modified. |
| Official OpenRouter docs | Read-only provider-routing, streaming and structured-output pages retrieved. | Documentation access is not runtime authorization or proof of a tested model. |
| OpenRouter runtime | Existing nonstream transport reused; SSE/controls validated through recorded and HTTP fixtures. | LIVE INFERENCE NOT VERIFIED. Separate current target grant/admission required, not old planning approval. |
| Direct compatible runtime | Real guarded HTTP transport exercised against an explicit synthetic loopback server. | LIVE SECOND PROVIDER = UNVERIFIED. Only administrator-approved endpoint IDs; no arbitrary URL input. |
| Drive / GitHub connector / Bright Data / Exa / Vercel / cloud DB / Figma | Not invoked for 7B; earlier availability is not reasserted. | No connector/session credentials copied into the deployed application. |

After integration fixtures passed, these **process environment names were absent**:
`OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `OPENAI_COMPATIBLE_API_KEY`,
`ROUTER_RUNTIME_REGISTRY_FILE`, `ROUTER_AUTH_FILE`, `ROUTER_APPROVALS_FILE`,
`ROUTER_LOCAL_INTERPRETATION_MODEL`. `router/.env` and the documented
`router/.local/runtime-registry.json` were absent. No secret values were printed;
this is not a search for credentials elsewhere or proof no provider account exists.

The app now supports explicit operator registry composition with `ROUTER_MODE=live`
and real shared authentication; fixture mode cannot load that registry. An app
connector is never automatically an application runtime adapter. See
`docs/API_COMPATIBILITY.md` for the central registry, scoped secret references,
endpoint/network controls, retention and exact unsupported subset.

## Upgrade-base refresh — September 7, 2026

This section records the upgrade-base check; see the 7B refresh above for current checks.

| Integration | Current development access / actual check | Deployed runtime boundary |
|---|---|---|
| Git / GitHub | Local refs/worktrees inspected; no remote configured. GitHub repository-list connector succeeded, returning no repositories. | No GitHub backend integration or push target configured. |
| Google Drive | Named running internship Doc reread successfully through the native document connector, read-only; its private text is not copied into this repo. | No Drive credentials or private assignment text in app/search. |
| Browser | Installed Playwright CLI/wrapper, real app on 5196/8026; fixture extraction, correction/reload and visible limitations audited, screenshot inspected, zero console errors/warnings. | Development tooling, not permission for a customer browser tool. |
| Bright Data / Exa | Search/extraction/status and Exa search discovered in the current tool inventory. Prior Bright Data setup is retained. No search/extraction/billable call made or credit balance assumed. | No authorized Bright Data/Exa runtime key/zone/budget. Prefer the prior setup if later public research is approved; do not require both. |
| Hugging Face / OpenRouter | Existing exact public-source parsers, public fixtures and protected runtime HTTP inspected. No new catalog/model-quality research performed. | Existing Hugging Face metadata worker path preserved, opt-in only. OpenRouter hosted planning adapter remains offline-tested, not live-verified; target runtime is a separate Lane 7 implementation. |
| Local inference | Existing Ollama adapter and saved September 6 run evidence inspected; offline regression checks pass. Audit app intentionally has no model configured, as shown in its UI. | No new local inference, model download or hosted target call in milestone 06. Earlier planning opt-in is not target-workload approval. |
| Database | Native PostgreSQL 17 binaries available. Separate loopback cluster verified clean migration and v2→v3 upgrade, old record preservation and concurrent caps. SQLite baseline/upgrade tests also pass. | No selected/approved Neon or Supabase project in app configuration. Both connectors are discoverable, not runtime authorization; no cloud provisioning or second database provider added. |
| Hosting | Vercel team/project read connectors succeeded; no Buildbox-named project in returned list. No existing app deployment link/config or Git remote. | No deployment selected, changed or performed. Managed credentials/TLS/retention review required before shared/public use. |
| Figma | No Figma URL/assets in selected app docs/config; no new design project needed for shared contracts. | Not a runtime dependency; no claim of design-file access. |

Official Chat Completions/model-list documentation was read only to define the
compatible subset; this is not an OpenAI provider integration or paid API call.
No account/key/zone creation, credential discovery, hidden credential-file search,
session-token copying, purchases, balance checks or production writes occurred.

Missing operational permissions should be requested together when a live target
test is next needed: exact target/model revision/provider endpoint, independent
server credential reference, approved data class/retention/egress, accepted license
policy and capability evidence, test count/token/deadline and maximum total spend.
For hosted execution, recorded operator approval is mandatory even if a key exists.
Milestone 06 does not need these permissions to finish offline contract work.

## Integration update — September 6, 2026

The foundation inventory below is historical. Integration verified actual local
API/worker calls, not just development connectors:

- Ollama 0.32.5 and a pre-existing cached `qwen2.5:0.5b` were found. An isolated
  loopback server with cloud disabled was used through the runtime adapter. No
  model download, provider credential or paid call was needed. Explicit per-plan
  opt-in and a 1,400-output-token/40-second bound apply. This is an uncalibrated
  control-plane parser, not a recommended target artifact.
- Runtime public research fetched official Hugging Face model metadata via the
  app worker, with opt-in and a zero-dollar provider cap. No private workflow
  text was sent. Exact source/observation records are retained with the plan.
- The OpenRouter runtime adapter is implemented and offline-tested against its
  current official request/endpoint documentation. No hosted permission/key/spend
  record was supplied; no hosted call is claimed verified. Separate role records
  support different model/provider-endpoint/key choices. Public research does not
  require an LLM, Bright Data, or Exa.
- Native PostgreSQL 17.11 is now available and passed an isolated UTF-8 database
  migration/persistence/concurrent-budget check. Docker's image-store I/O error
  still exists; integration did not repair or reset it.
- HTTP Basic authentication backed by operator-provisioned PBKDF2 identities was
  verified through the real local API and browser, including cross-tenant denial.
  This is not permission for shared/public deployment; non-loopback use needs TLS.

See [local run and permission boundaries](../router/INTEGRATION_RUN.md) and the
integration handoff for exact evidence, commands and remaining release gates.

## Historical foundation inventory

Discovery/read checks: September 6, 2026. Connector access is development-time
access only; it does **not** grant deployed application access. No session token,
private requirements text, provider key or account identifier was copied here.

| Integration | Development-time verification | Runtime status / authorization |
|---|---|---|
| Git / GitHub | Local Git works; no remote or commits at intake. GitHub repository-list read succeeded but returned no repositories. | No GitHub runtime integration needed. A remote/selected repository needs user direction before linking/pushing. |
| Google Drive | The specified running internship Doc was fetched successfully, read-only. | No Drive adapter or session credentials in product. Customer-data access needs separate scoped authorization. |
| Bright Data | Search/extraction tools discovered; `session_stats` read succeeded. No search or scrape was made. Credits were not checked or assumed. Skill read; no session configuration changed. | Offline search adapter raises a typed unsupported error. Future runtime key/zone/spend approval required; not a Codex credential. |
| Exa | Search tool discovered in this session; execution/credits not verified because this milestone makes no billable searches. | Optional alternative, not a dependency. Separate authorization and runtime credential required. |
| Inference | No provider/role configuration in selected app because none existed. Named environment variables below absent. | Injected `InferencePort`; offline adapter rejects calls. Interpretation/evaluation role configuration remains an integration-owner task. No live client on import. |
| Neon | `list_projects` attempted; service requires an organization ID. No approved Buildbox database established. | Not configured or provisioned. Organization/project approval needed before any managed connection. |
| Supabase | Connector discovered; no Supabase config or approved project in workspace. Not selected alongside Neon by default. | Not a runtime dependency. Do not provision a second database. |
| Vercel | Team/project reads succeeded; 11 projects returned, none named Buildbox. No `.vercel` or deployment convention in selected repository. | Not linked/deployed. Real auth and an approved hosting target required; fixture identity must never be public. |
| Browser / Playwright | `node`, `npm`, `npx` available; local browser verification results in foundation handoff. | Development test tooling only. No customer browser/action execution. |
| Figma | No existing project design reference or local design config discovered; no new design project requested. | Not required for this milestone; no access claim made. |
| PostgreSQL / Docker | Docker daemon responds; image listing fails with existing image-store I/O error. No native Postgres binary found in checked Homebrew/Application locations. | Local Compose recipe only; actual PostgreSQL runtime verification blocked. Explicit SQLite fixtures work independently. |

## Credential presence check

At discovery the following process environment names were **absent**:
`DATABASE_URL`, `NEON_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`VERCEL_TOKEN`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `BRIGHT_DATA_API_TOKEN`,
`EXA_API_KEY`. This checks only those names in the process environment; it is not
a search for hidden credentials or proof that no account exists.

The application currently reads only `ROUTER_MODE`, `ROUTER_IDENTITY_MODE` and
`ROUTER_DATABASE_URL`. The local fixture identity is a constant, not a secret.
No billable inference/search, cloud database write, purchase, deploy or push was
performed. Initial package installation uses public package registries; tests and
the fixture path are offline after installation.
