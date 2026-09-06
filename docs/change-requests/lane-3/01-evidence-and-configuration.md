# Lane B request: version rich evidence and configuration contracts

Base: `b36437fc91b717b3978f977ec3cdf084c8206a5b`.
Status: requested; no shared contract or generated file is changed by this lane.

## Required integration change

Version the shared evidence/configuration contracts to carry the data currently
preserved in the lane's private research ledger:

- Evidence subject kind/ID, source type/locator, retained-content digest,
  publication/retrieval/test dates, `observed_at`, `expires_at`, raw metric/unit,
  benchmark name/version/split, harness/settings, sample size, limitations and
  publisher-declared versus independently measured status.
- Artifact publisher/repository identity, exact revision, declared access/gate,
  weight-file/access evidence, license declaration source and review state,
  explicit modality facts and release-date unknowns.
- Endpoint identity separate from artifact identity; optional served revision,
  deployment mode, provider-specific parameter declarations and restrictions,
  effective context/prompt/output ceilings, region/privacy/hardware/quantization,
  and separate component prices with units/conditional rules.
- Optional or separately bound prompt/harness references. Public endpoint metadata
  cannot supply these customer/integration configuration choices.
- A typed research result carrying partial/stale/conflict/unavailable outcomes.

The existing `cost_per_1k_tokens` scalar cannot represent different input/output,
request, image, or conditional prices. It must stay Unknown until the integration
owner defines the usage mix and all relevant price conditions. A publisher's
repository revision is not proof of the revision actually served by a gateway.

## Executable failing example under v1

`router/tests/research/test_shared_contract_requests.py` verifies that adding
`subject_id`, `source_locator`, or `expires_at` to canonical `Evidence` fails with
`extra_forbidden`. The test passes by asserting that rejection; it is a reproduction
of missing contract capacity, not a claim that the richer contract exists.

Public metadata supplies no real prompt/harness references. Consequently the
unbound public snapshot has eight artifacts, one endpoint declaration in its
ledger, and zero canonical configurations. A fabricated reference would conceal
that gap. The lane's explicit `ConfigurationBinding` accepts integration-provided
references and retains Unknown workload cost/latency. It does not clear gated or
unknown access.

## Compatibility and migration

Do not add a second public `Evidence` or `CandidateConfiguration` in lane code.
Private ledger records compose the existing canonical types and do not cross
the frozen lane return boundary. Promote agreed fields through a versioned shared
schema, regenerate OpenAPI/TypeScript, and preserve reading existing v1 snapshots.
Old evidence must retain Unknown for unavailable fields rather than retroactively
acquiring a timestamp, unit, license clearance, or quality measurement.

Integration must update eligibility/ranking to honor these fields before exposing
real candidates. Lane B does not edit selection, API composition, generated types,
or Lane A. No shared files were patched to make a test pass.
