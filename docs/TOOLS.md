# Tool access and runtime boundary

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
