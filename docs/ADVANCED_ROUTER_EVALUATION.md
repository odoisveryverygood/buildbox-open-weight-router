# Advanced router evaluation — September 13, 2026

This is a **router-behavior evaluation**, not evidence of real model quality.
No vendor requests, paid inference, fresh search or model downloads were performed.
Full machine-readable run: `router/output/advanced-evaluation.json` (local generated
artifact; reproduce with the command below). This document retains its concise result.

## Bounded workload suite

`router-behavior-1`, catalog `advanced-catalog-v1`, capability schema
`capabilities-1`, analyzer `workload-rules-1`, balanced@1 versus quality@1.
Each decision retains the exact catalog digest, profile, candidate ranking and
policy configuration. Every executed run retains exact policy/prompt/workflow
references, outputs, usage and attempt traces in the report.

| Workload | Default policy execution | Model attempts | Check |
|---|---|---:|---|
| Extraction | succeeded | 1 | Synthetic fixture integrity |
| Summarization | succeeded | 1 | Synthetic fixture integrity |
| Code generation | succeeded | 1 | Synthetic fixture integrity, not code correctness |
| Debugging | succeeded | 1 | Synthetic fixture integrity, not bug repair |
| Structured extraction | succeeded | 1 | Runtime JSON schema + fixture integrity |
| Tool use | correctly blocked | 0 | Automatic planner cannot grant/construct an unreviewed tool graph |
| Mathematical reasoning | succeeded | 1 | Synthetic fixture integrity, not mathematical correctness |
| Long-context synthesis | succeeded | 1 | Context gate + fixture integrity; input envelope is simulated |
| Multi-stage | succeeded | 3 | Real dependency binding and persisted stage outputs |

Nine decision comparisons; eight executed workflows; ten actual local HTTP model
attempts against the same synthetic server. One synthetic sample per executed case.
Default versus quality selected identical pins on this particular nine-case fixture
suite: **zero disagreements**, not proof that the policies are equivalent. The
separate J test demonstrates a genuine speed-versus-quality decision difference.

Local planning-and-persistence wall time in the recorded run ranged from **4.85 to
9.29 ms** across nine cases. These values are machine/run-dependent, not an SLA,
gateway-only benchmark or model inference latency. Attempt records separately
retain gateway/upstream timing, tokens, declared/recorded synthetic costs and errors.
Synthetic upstream reports zero actual charge; forecast prices are hand-authored
routing fixtures, not provider prices.

## D–J behavior checks

- D: long-context requirement excludes the small configuration.
- E: local/self-hosted/no-retention requirements select the declared local fixture;
  runtime also checks the actual approved loopback transport.
- F: hard cost ceiling excludes more expensive configurations.
- G: extraction/synthesis select the small configuration; reasoning selects medium.
- H: the first output fails a literal reviewed validator; a permitted higher-evidence
  configuration succeeds. Both attempts and the failed validation persist. Repeatable.
- I: three recorded synthetic transport failures open the medium deployment circuit;
  another deployment of the same model artifact is selected.
- J: speed selects small; quality selects medium. What-if performs no inference,
  preserves the old decision, and cannot reuse its admission for a new draft.

Additional tests execute parallel three-branch/synthesis and generate/verify DAGs
through the real existing worker. They do not establish independent verification,
conditional repair, or an advantage over a real single-model baseline.

## Quality and coverage limits

The literal `VALID` rubric only checks fixture identity/transport integrity. It is
not a semantic correctness rubric. No real-model pass rate, accuracy improvement,
statistical significance, production reliability, or cost savings is claimed.
Performance fixtures explicitly have unknown measurement date/sample size; their
values must never be imported into a public/live catalog as measured results.

The full studio regression separately compares two configurations on two reviewed
synthetic examples: four cells, two expected exact-match failures retained, no
automatic winner. Original A–C continues to cover genuine SSE framing/tool-ID/JSON
plumbing against synthetic upstreams.

## Reproduce

From `router/`:

```sh
uv run python -m tests.gateway.evaluate_advanced --output output/advanced-evaluation.json
uv run pytest tests/gateway/test_advanced_router.py -q
```

The evaluation command creates fresh isolated fixture storage and bounded loopback
requests. Ordinary tests need no credentials. Historical run IDs/times differ between
executions; expected constraint, routing and validation behavior is deterministic.
