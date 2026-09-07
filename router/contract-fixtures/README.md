# Shared sandbox contract fixtures

`sandbox-policy-v2.json` is synthetic, including its model/configuration identity.
It proves executable type/budget/prompt wiring only. It is not a released model,
workload result, key, operator permission, admission, or runnable deployment.

Both lanes consume the same JSON and generated TypeScript/OpenAPI schemas. Generate
with `uv run python scripts/generate_sandbox_fixture.py`; drift is checked by
`make check-generated`. Never edit it from a lane or promote it into public catalog
evidence. Shared tests in `tests/integration/test_execution_contracts.py` supply
typed synthetic response/SSE/admission examples, with explicitly test-only guards.

The API defaults to no runtime services. Do not make an HTTP fixture grant endpoint
to simplify UI tests. Use isolated offline port injection when exercising the API
composition, and label synthetic output comparisons accordingly.
