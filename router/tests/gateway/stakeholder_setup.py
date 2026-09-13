"""Explicit deterministic demo data. Not imported by normal product composition.

Uses existing synthetic configurations, real selector, persistence and gateway.
No model-quality evidence or provider connection is invented.
"""

import json
from datetime import UTC, datetime, timedelta

from buildbox_router.contracts import (
    Binding,
    ConfigurationEligibility,
    Intake,
    Interpretation,
    Node,
    TargetRequirements,
    Workflow,
)
from buildbox_router.demo_contracts import DemoManifest, DemoScenario
from buildbox_router.execution_contracts import (
    ExecutablePolicy,
    ExecutableStage,
    PromptRevision,
    RouteAlias,
    ToolDefinition,
    VersionRef,
    digest,
)
from buildbox_router.execution_storage import append
from buildbox_router.planning_contracts import PlanInput, PlanningResult
from buildbox_router.runtime_contracts import ReadOnlyPacket

from .test_unblock import sse, wire


def setup_demo(rt, state, services):
    now = datetime.now(UTC)
    full = ("max_tokens", "temperature", "stream", "tools", "tool_choice", "response_format")
    basic = ("max_tokens", "temperature", "stream")
    catalog = rt.catalog.model_copy(
        update={
            "eligibility": tuple(
                ConfigurationEligibility(
                    configuration_id=c.id,
                    artifact_id=c.artifact_id,
                    weights_access=rt.fact(True),
                    license_policy=rt.fact(True),
                    input_modalities=rt.fact(("text",)),
                    supported_parameters=rt.fact(full if c.id == "fixture-medium-local" else basic),
                    deployment=rt.fact("api"),
                    observed_at=now.isoformat(),
                    expires_at=(now + timedelta(hours=1)).isoformat(),
                )
                for c in rt.catalog.configurations
            )
        }
    )
    workspace = state.registry.workspaces[0]
    targets = tuple(
        rt.target.model_copy(
            update={
                "configuration": c,
                "endpoint": rt.target.endpoint.model_copy(
                    update={
                        "supported_parameters": rt.fact(
                            full if c.id == "fixture-medium-local" else basic
                        )
                    }
                ),
            }
        )
        for c in catalog.configurations
        if c.id in ("fixture-small-local", "fixture-medium-local")
    )
    state.registry = state.registry.model_copy(
        update={
            "workspaces": (
                workspace.model_copy(
                    update={
                        "catalogs": (catalog,),
                        "targets": targets,
                        "grants": (
                            workspace.grants[0].model_copy(
                                update={
                                    "configuration_ids": tuple(t.configuration.id for t in targets)
                                }
                            ),
                        ),
                        "read_only_packets": (
                            ReadOnlyPacket(
                                tool_id="sample-lookup-support",
                                rows={"shipping": "Standard shipping takes 3 business days."},
                                source_label="Synthetic support policy v1",
                                provenance="Hand-authored demonstration, no customer system",
                                data_class="synthetic",
                                observed_at=now,
                                expires_at=now + timedelta(hours=1),
                            ),
                        ),
                    }
                ),
            )
        }
    )
    selector, store = services.selector, rt.store
    planning = services.storage
    scenarios = []

    def build(name, title, task, expected, *, pinned=None, capabilities=False):
        intake = Intake(description=task, constraints=rt.policy.workflow.constraints)
        value = planning.submit(
            "alice", "demo-seed-" + name, PlanInput(intake=intake, proposal_mode="single_stage")
        )
        claimed = planning.claim()
        assert claimed and claimed[1].id == value.job.id
        workflow = Workflow(
            id=value.plan.id,
            version=1,
            title=task,
            inputs=("input",),
            nodes=(
                Node(
                    id="respond",
                    kind="llm",
                    purpose=task,
                    inputs={"input": Binding(source="input", output="value", from_input=True)},
                ),
            ),
            constraints=intake.constraints,
            requirements=TargetRequirements(
                tool_calling=capabilities, structured_output=capabilities
            ),
            provenance=rt.fact(True).provenance,
        )
        rec = selector.recommend(workflow, catalog, value.job.id)
        selected = pinned or rec.assignments[0].configuration_id
        assert selected in rec.filter_result.eligible
        planning.complete_planning(
            "alice",
            claimed[1],
            PlanningResult(
                plan_id=workflow.id,
                version=1,
                workflow=workflow,
                catalog=catalog,
                interpretation=Interpretation(status="ready", workflow=workflow),
                recommendation=rec,
                exclusions=rec.filter_result.excluded,
                status="provisional",
                fixture=True,
                assumptions=(
                    "Preconfigured demo requirements; not live interpretation or quality evidence",
                ),
            ),
        )
        prompt = PromptRevision(
            id="demo-" + name + "-prompt",
            version=1,
            template=task + "\nSample: {{input}}",
            variables={"input": "text"},
        )
        budget = rt.policy.stages[1].budget.model_copy(update={"max_input_tokens": 2048})
        policy = ExecutablePolicy(
            id="demo-" + name,
            version=1,
            plan=VersionRef(id=workflow.id, version=1),
            workflow=workflow,
            catalog_id=catalog.id,
            input_types={"input": "text"},
            prompts=(prompt,),
            stages=(
                ExecutableStage(
                    node_id="respond",
                    configuration_id=selected,
                    input_types={"input": "text"},
                    output_types={"result": "text"},
                    prompt=VersionRef(id=prompt.id, version=1),
                    budget=budget,
                ),
            ),
            budget=budget,
        )
        store.save_prompt("alice", prompt)
        ref, admission = save(policy)
        alternative = None
        other_admission = None
        if not capabilities:
            other = next(t.configuration.id for t in targets if t.configuration.id != selected)
            alternate = policy.model_copy(
                update={
                    "id": policy.id + "-alternative",
                    "stages": (policy.stages[0].model_copy(update={"configuration_id": other}),),
                }
            )
            alternative, other_admission = save(alternate)
        explanation = (
            f"Selected {selected} because the reviewer explicitly pinned it for this complex review. "
            "It passes the same hard constraints. The cheaper candidate remains eligible; no measured intelligence advantage is claimed."
            if pinned
            else f"Selected {selected}: it satisfies tool calling and structured-output requirements within the cost and region limits. "
            "The cheaper small configuration lacks the required declared parameters."
            if capabilities
            else f"Selected {selected}: it meets the cost and region limits and has the lowest supported catalog unit price among eligible candidates. "
            "Latency is not benchmarked, so speed is not a selection claim."
        )
        return DemoScenario(
            id=name,
            title=title,
            task=task,
            requirements=(
                "Open-weight policy (synthetic evidence)",
                "Region: local",
                "Catalog ceiling: $1 / 1k tokens (synthetic)",
                "Tools + JSON required" if capabilities else "Text output; no tools required",
            ),
            policy=ref,
            plan=policy.plan,
            alias=policy.id + "-alias",
            admission_id=admission,
            selected=selected,
            alternative=alternative,
            alternative_admission=other_admission,
            explanation=explanation,
            assessments=selector.assess(workflow, catalog),
            inputs={"input": task},
            expected=expected,
            tools=(
                ToolDefinition.model_validate(
                    {
                        "type": "function",
                        "function": {
                            "name": "lookup_support",
                            "description": "Simulated read-only shipping lookup",
                            "parameters": {
                                "type": "object",
                                "properties": {"key": {"type": "string"}},
                                "required": ["key"],
                                "additionalProperties": False,
                            },
                            "strict": True,
                        },
                    }
                ),
            )
            if capabilities
            else (),
        )

    def save(policy):
        store.create_policy("alice", policy)
        ref = VersionRef(id=policy.id, version=policy.version)
        admission_id = policy.id + "-admit"
        admission = rt.admission.model_copy(
            update={
                "id": admission_id,
                "policy": ref,
                "policy_digest": digest(policy),
                "configuration_ids": tuple(
                    dict.fromkeys(
                        c
                        for s in policy.stages
                        for c in (s.configuration_id,) + s.fallback_configuration_ids
                        if c
                    )
                ),
            }
        )
        with store.engine.begin() as conn:
            append(conn, "alice", "admission", admission_id, 1, admission)
        store.create_alias(
            "alice",
            RouteAlias(
                id=policy.id + "-alias",
                policy=ref,
                node_id="respond",
                configuration_id=policy.stages[0].configuration_id,
                created_at=now,
            ),
        )
        return ref, admission_id

    scenarios.append(
        build(
            "fast",
            "A · Everyday summary",
            "Summarize this meeting: launch is Friday; Maya owns QA; the remaining risk is a late supplier.",
            "Launch: Friday. Owner: Maya (QA). Risk: supplier delay.",
        )
    )
    scenarios.append(
        build(
            "review",
            "B · Complex review",
            "Review a payment retry design. Explain idempotency, duplicate-charge risks and a bounded retry policy.",
            "Use an idempotency key per logical payment. Reconcile unknown results before retrying. Bound retries and never repeat a confirmed charge.",
            pinned="fixture-medium-local",
        )
    )
    scenarios.append(
        build(
            "tools",
            "C · Tools + JSON",
            "Look up the shipping policy with a read-only tool and return structured output with category and reply.",
            {"category": "shipping", "reply": "Standard shipping takes 3 business days."},
            capabilities=True,
        )
    )
    first = scenarios[0]
    original = store.policy("alice", first.policy).policy
    fb_budget = original.budget.model_copy(update={"max_model_calls": 2, "max_attempts": 2})
    fb = original.model_copy(
        update={
            "id": "demo-fallback",
            "budget": fb_budget,
            "stages": (
                original.stages[0].model_copy(
                    update={
                        "fallback_configuration_ids": ("fixture-medium-local",),
                        "budget": fb_budget,
                    }
                ),
            ),
        }
    )
    ref, admit = save(fb)
    fallback = first.model_copy(
        update={
            "id": "fallback",
            "title": "Safe fallback",
            "policy": ref,
            "alias": "demo-fallback-alias",
            "admission_id": admit,
            "explanation": "The small configuration is selected first. This explicit test injects a 503 before any response is committed; the policy permits one medium-configuration fallback. No mixed-model answer or side effect is allowed.",
        }
    )
    failures = set()

    def respond(body):
        state.status, state.delay, state.parts = 200, 0.07, None
        messages = json.dumps(body["messages"])
        output = (
            scenarios[2].expected
            if "shipping" in messages.lower()
            else scenarios[1].expected
            if "payment" in messages.lower()
            else first.expected
        )
        content = json.dumps(output) if isinstance(output, dict) else output
        if "DEMO_FAIL_ONCE" in messages and messages not in failures:
            failures.add(messages)
            state.status, state.result = (
                503,
                {"error": {"message": "Controlled synthetic unavailability"}},
            )
            return
        calls = None
        if body.get("tools") and body["messages"][-1]["role"] != "tool":
            calls = [
                {
                    "id": "call-demo-shipping",
                    "type": "function",
                    "function": {"name": "lookup_support", "arguments": '{"key":"shipping"}'},
                }
            ]
            content = None
        state.result = wire(content=content, calls=calls)
        if body.get("stream"):
            if calls:
                state.parts = [
                    sse({"tool_calls": [dict(calls[0], index=0)]}),
                    sse({}, "tool_calls"),
                ]
            else:
                state.parts = [
                    sse({"content": content[i : i + 18]}) for i in range(0, len(content), 18)
                ] + [sse({}, "stop")]
            state.parts += [
                sse(
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                        "cost": 0,
                    }
                ),
                b"data: [DONE]\n\n",
            ]

    state.respond = respond
    return DemoManifest(catalog=catalog, scenarios=tuple(scenarios), fallback=fallback)
