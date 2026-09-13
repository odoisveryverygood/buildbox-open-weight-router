"""Opt-in, bounded loopback evaluation; no vendor calls or model-quality inference.

uv run python -m tests.gateway.evaluate_advanced --output output/advanced-evaluation.json
Creates an isolated fixture database; never consumes a user's existing database.
"""

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

from buildbox_router.contracts import WorkloadProfile
from buildbox_router.execution_contracts import (
    TransitionRequest,
    VersionRef,
    WorkflowRunRequest,
    digest,
)
from buildbox_router.execution_storage import append
from buildbox_router.routing_contracts import PreviewRequest, RouterPolicy, WhatIfRequest
from buildbox_router.routing_service import draft, preview, what_if

from .browser_fixture import create_fixture_app
from .conftest import ctx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ["ROUTER_ACCEPTANCE_SETUP"] = "stakeholder"
    app = create_fixture_app()
    rt, _ = app.state.synthetic_context
    # Use the same composed runner as the API. No direct model path.
    from buildbox_router.composition import product_services
    from buildbox_router.execution_composition import compose_execution
    from buildbox_router.planning_storage import PlanningStorage

    services = product_services(PlanningStorage(rt.store.engine))
    execution = compose_execution(
        rt.store, app.state.synthetic_context[1].registry, services.selector, retention_seconds=3600
    )
    catalog = app.state.intelligence_catalogs["alice"]["advanced-catalog-v1"]
    cases = (
        ("extraction", "Extract receipt fields", {}),
        ("summarization", "Summarize meeting notes", {}),
        ("coding", "Implement a pure sorting function", {}),
        ("debugging", "Debug an index error", {}),
        (
            "structured_extraction",
            "Extract schema JSON",
            {"structured_output": "schema_json", "required": ("text_input", "schema_json")},
        ),
        (
            "tool_use",
            "Use the reviewed lookup tool",
            {"tools": ("lookup",), "required": ("text_input", "tools"), "max_tool_calls": 1},
        ),
        ("mathematics", "Reason about a combinatorics problem", {}),
        ("long_context", "Synthesize a long document", {"input_tokens": 16384}),
        ("general", "Extract, reason and synthesize", {"strategy": "multi_stage"}),
    )
    rows = []
    for index, (task, description, extra) in enumerate(cases):
        profile = WorkloadProfile.model_validate(
            {"task": task, "input_tokens": 4096, "output_tokens": 128, **extra}
        )
        start = time.perf_counter()
        original = preview(
            rt.store,
            "alice",
            PreviewRequest(description=description, catalog_id=catalog.id, overrides=profile),
            catalog,
        )
        elapsed = (time.perf_counter() - start) * 1000
        experimental, shadow = what_if(
            rt.store,
            "alice",
            original,
            WhatIfRequest(policy=RouterPolicy(id="quality", weights={"quality": 1})),
        )
        execution_result = None
        if original.status == "ready":
            policy = draft(rt.store, "alice", original)
            ref = VersionRef(id=policy.id, version=1)
            admission = rt.admission.model_copy(
                update={
                    "id": f"evaluation-{index}-admit",
                    "policy": ref,
                    "policy_digest": digest(policy),
                    "configuration_ids": tuple(
                        dict.fromkeys(s.configuration_id for s in policy.stages)
                    ),
                }
            )
            with rt.store.engine.begin() as conn:
                append(conn, "alice", "admission", admission.id, 1, admission)
            rt.store.transition(
                "alice",
                ref,
                TransitionRequest(
                    expected_sequence=1, status="sandbox_enabled", admission_id=admission.id
                ),
            )
            sample = f"ADVANCED_EVAL_{index}: public synthetic example for {task}."
            run = asyncio.run(
                execution.workflows.submit(
                    ctx(), WorkflowRunRequest(policy=ref, inputs={"input": sample})
                )
            )
            for _ in range(300):
                current = asyncio.run(execution.workflows.get(ctx(), run.id))
                if current.status not in ("queued", "running"):
                    break
                time.sleep(0.1)
            attempts = rt.store.attempts("alice", run.id)
            outputs = rt.store.outputs_for_run("alice", run.id)
            execution_result = {
                "input": sample,
                "run": current.model_dump(mode="json"),
                "attempts": [a.model_dump(mode="json") for a in attempts],
                "outputs": [o.model_dump(mode="json") for o in outputs],
                "fixture_integrity_pass": current.status == "succeeded"
                and all("VALID" in str(o.value) for o in outputs),
                "model_quality": None,
            }
        rows.append(
            {
                "case": task,
                "profile": original.profile.model_dump(mode="json"),
                "decision_id": original.id,
                "catalog_digest": original.catalog_digest,
                "policy": original.router_policy.model_dump(),
                "stages": [s.model_dump(mode="json") for s in original.stages],
                "blockers": original.blockers,
                "planner_wall_ms": elapsed,
                "experimental_decision": experimental.id,
                "shadow": shadow.model_dump(mode="json"),
                "execution": execution_result,
            }
        )
    report = {
        "suite": "router-behavior-1",
        "case_count": len(rows),
        "fixture_catalog": catalog.id,
        "model_quality_conclusion": False,
        "limitations": [
            "All capability, task scores, prices and upstream responses are explicitly synthetic.",
            "Wall-clock timings measure this local software run, not real model latency.",
            "Literal VALID and JSON schema checks test fixture integrity, not semantic task quality.",
            "A/B compares decisions only; experimental routes are not executed.",
            "Named-tool automatic planning must block until a reviewed tool graph is supplied.",
        ],
        "cases": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    executed = [r for r in rows if r["execution"]]
    assert len(executed) == 8 and all(r["execution"]["fixture_integrity_pass"] for r in executed)
    assert rows[5]["blockers"] and rows[5]["execution"] is None
    print(
        f"PASS: 9 A/B routing cases, 8 synthetic workflow executions, 1 expected tool-authority block; model quality NOT evaluated. Report: {args.output}"
    )


if __name__ == "__main__":
    main()
