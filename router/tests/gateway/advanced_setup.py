"""D–J: explicitly synthetic capability/performance data on the existing loopback adapter."""

import json
from datetime import UTC, datetime, timedelta

from buildbox_router.contracts import (
    CapabilityObservation,
    ConfigurationEligibility,
    DeploymentIntelligence,
    Fact,
    PerformanceEvidence,
    WorkloadProfile,
)
from buildbox_router.execution_contracts import CircuitPolicy, VersionRef, digest
from buildbox_router.execution_storage import append
from buildbox_router.gateway.health import DeploymentHealth
from buildbox_router.routing_contracts import AdvancedScenario, PreviewRequest, RouterPolicy
from buildbox_router.routing_service import draft, preview

from .test_unblock import sse, wire


def advanced_catalog(base, now=None, health=False):
    now = now or datetime.now(UTC)
    expires = now + timedelta(hours=4)
    provenance = base.evidence[0].provenance
    artifacts = tuple(
        base.artifacts[0].model_copy(
            update={"id": f"advanced-{name}-artifact", "name": f"SYNTHETIC {name} artifact"}
        )
        for name in ("small", "medium", "large")
    )
    configurations, intelligence, performance, eligibility = [], [], [], []
    for i, name in enumerate(("small", "medium", "large", "equivalent")):
        identifier = f"{'health' if health else 'advanced'}-{name}-loopback"
        artifact = artifacts[1 if name == "equivalent" else i].id
        cost, latency = ((0.2, 100), (1.0, 400), (3.0, 800), (1.1, 450))[i]
        config = base.configurations[0].model_copy(
            update={
                "id": identifier,
                "artifact_id": artifact,
                "cost_per_1k_tokens": Fact[float](value=cost / 1000, provenance=provenance),
            }
        )
        configurations.append(config)
        values = {
            "text_input": True,
            "text_output": True,
            "json_output": True,
            "schema_json": name != "small",
            "tools": name != "small",
            "code_output": True,
            "streaming": True,
            "context_tokens": 8192 if name == "small" else 131072,
            "max_output_tokens": 4096,
            "latency_ms": latency,
            "throughput_tokens_s": 100 if name == "small" else 30,
            "input_usd_per_million": cost,
            "output_usd_per_million": cost * 2,
            "request_usd": 0,
            "local": name == "small",
            "self_hosted": name == "small",
            "retention_days": 0 if name == "small" else 7,
            "privacy_class": "local_only" if name == "small" else "synthetic-approved-hosted",
            "success_rate": 0.99,
            "backends": ["openai-compatible"],
            "quantization": "fixture-only",
            "parameters_billion": (3, 14, 70, 14)[i],
        }
        facts = {
            k: CapabilityObservation(
                fact=Fact(value=v, provenance=provenance),
                basis="synthetic",
                observed_at=now,
                expires_at=expires,
            )
            for k, v in values.items()
        }
        intelligence.append(DeploymentIntelligence(configuration_id=identifier, facts=facts))
        params = ("max_tokens", "stream", "temperature") + (
            ("response_format", "tools", "tool_choice") if name != "small" else ()
        )
        eligibility.append(
            ConfigurationEligibility(
                configuration_id=identifier,
                artifact_id=artifact,
                weights_access=Fact(value=True, provenance=provenance),
                license_policy=Fact(value=True, provenance=provenance),
                input_modalities=Fact(value=("text",), provenance=provenance),
                supported_parameters=Fact(value=params, provenance=provenance),
                deployment=Fact(
                    value="self_hosted" if name == "small" else "api", provenance=provenance
                ),
                observed_at=now.isoformat(),
                expires_at=expires.isoformat(),
            )
        )
        for task in (
            "extraction",
            "summarization",
            "classification",
            "coding",
            "debugging",
            "mathematics",
            "long_context",
            "tool_use",
            "structured_extraction",
            "research",
            "general",
        ):
            score = (
                (0.96, 0.82, 0.8, 0.82)
                if task in ("extraction", "summarization", "classification")
                else (0.35, 0.95, 0.88, 0.94)
            )[i]
            performance.append(
                PerformanceEvidence(
                    id=f"{identifier}-{task}",
                    configuration_id=identifier,
                    task=task,
                    benchmark="Synthetic routing behavior suite",
                    benchmark_version="1",
                    split="fixture",
                    harness="deterministic-values-1",
                    settings="not inference",
                    raw_metric=score,
                    unit="fixture fraction",
                    normalized_score=score,
                    normalization="identity on synthetic [0,1] values",
                    sample_size=None,
                    measured_at=None,
                    retrieved_at=now,
                    expires_at=expires,
                    source_locator=f"advanced_setup.py:{name}/{task}",
                    provenance=provenance,
                    origin="synthetic",
                    reviewed=True,
                    limitations=(
                        "Hand-authored routing behavior values; no model quality was measured",
                    ),
                )
            )
    return base.model_copy(
        update={
            "id": "health-catalog-v1" if health else "advanced-catalog-v1",
            "artifacts": artifacts,
            "configurations": tuple(configurations),
            "eligibility": tuple(eligibility),
            "intelligence": tuple(intelligence),
            "performance": tuple(performance),
        }
    )


def scenario_requests(catalog_id):
    base = {"input_tokens": 4096, "output_tokens": 128}
    quality = RouterPolicy(id="quality", weights={"quality": 1.0})
    return (
        (
            "D",
            "Long context",
            PreviewRequest(
                description="Synthesize a long-context document",
                catalog_id=catalog_id,
                overrides=WorkloadProfile(
                    **(base | {"task": "long_context", "input_tokens": 16384})
                ),
            ),
        ),
        (
            "E",
            "Privacy",
            PreviewRequest(
                description="Summarize private records locally with no retention",
                catalog_id=catalog_id,
                overrides=WorkloadProfile(
                    **(base | {"local_only": True, "self_hosted_only": True, "no_retention": True})
                ),
            ),
        ),
        (
            "F",
            "Hard budget",
            PreviewRequest(
                description="Write a function under a strict budget",
                catalog_id=catalog_id,
                policy=quality,
                overrides=WorkloadProfile(
                    **(base | {"task": "coding", "max_cost_micro_usd": 1000})
                ),
            ),
        ),
        (
            "G",
            "Specialist stages",
            PreviewRequest(
                description="Extract requirements then implement code and summarize",
                catalog_id=catalog_id,
                policy=quality,
                overrides=WorkloadProfile(**(base | {"task": "coding", "strategy": "multi_stage"})),
            ),
        ),
        (
            "H",
            "Validation escalation",
            PreviewRequest(
                description="Solve a coding task and verify required acceptance terms",
                catalog_id=catalog_id,
                overrides=WorkloadProfile(**(base | {"task": "coding", "strategy": "cheap_first"})),
                required_terms=("VALID",),
            ),
        ),
        (
            "I",
            "Deployment health",
            PreviewRequest(
                description="Review code with current deployment health",
                catalog_id=catalog_id,
                policy=quality,
                overrides=WorkloadProfile(**(base | {"task": "coding"})),
            ),
        ),
        (
            "J",
            "Policy what-if",
            PreviewRequest(
                description="Implement a function",
                catalog_id=catalog_id,
                policy=RouterPolicy(id="speed", weights={"latency": 1.0}),
                overrides=WorkloadProfile(**(base | {"task": "coding"})),
            ),
        ),
    )


def setup_advanced(rt, state, services, manifest):
    catalog = advanced_catalog(manifest.catalog)
    health_catalog = advanced_catalog(manifest.catalog, health=True)
    workspace = state.registry.workspaces[0]
    endpoint = workspace.targets[0].endpoint.model_copy(
        update={
            "context_tokens": rt.fact(131072),
            "max_prompt_tokens": rt.fact(120000),
            "max_completion_tokens": rt.fact(4096),
        }
    )
    targets = tuple(
        workspace.targets[0].model_copy(
            update={
                "configuration": c,
                "catalog_id": snap.id,
                "endpoint": endpoint.model_copy(
                    update={"supported_parameters": snap.eligibility[i].supported_parameters}
                ),
            }
        )
        for snap in (catalog, health_catalog)
        for i, c in enumerate(snap.configurations)
    )
    state.registry = state.registry.model_copy(
        update={
            "workspaces": (
                workspace.model_copy(
                    update={
                        "catalogs": workspace.catalogs + (catalog, health_catalog),
                        "targets": workspace.targets + targets,
                        "grants": (
                            workspace.grants[0].model_copy(
                                update={
                                    "configuration_ids": workspace.grants[0].configuration_ids
                                    + tuple(t.configuration.id for t in targets)
                                }
                            ),
                        ),
                    }
                ),
            )
        }
    )
    scenarios = []
    for identifier, title, request in scenario_requests(catalog.id):
        if identifier == "I":
            request = request.model_copy(update={"catalog_id": health_catalog.id})
            health = DeploymentHealth(rt.store)
            cp = CircuitPolicy(cooldown_seconds=3600)
            health.acquire("alice", "health-medium-loopback", health_catalog.id, cp)
            for _ in range(3):
                health.observe(
                    "alice",
                    "health-medium-loopback",
                    health_catalog.id,
                    cp,
                    failure="provider_failure",
                    latency_ms=1,
                )
        result = preview(
            rt.store, "alice", request, health_catalog if identifier == "I" else catalog
        )
        policy = draft(rt.store, "alice", result)
        # Synthetic operator-only provisioning. Never exposed as a grant endpoint.
        configs = tuple(
            dict.fromkeys(
                c
                for s in policy.stages
                for c in (s.configuration_id, *s.fallback_configuration_ids)
                if c
            )
        )
        admission = rt.admission.model_copy(
            update={
                "id": "advanced-" + identifier + "-admit",
                "policy": VersionRef(id=policy.id, version=1),
                "policy_digest": digest(policy),
                "configuration_ids": configs,
                "expires_at": datetime.now(UTC) + timedelta(hours=1),
            }
        )
        with rt.store.engine.begin() as conn:
            append(conn, "alice", "admission", admission.id, 1, admission)
        scenarios.append(
            AdvancedScenario(
                id=identifier,
                title=title,
                request=request,
                decision_id=result.id,
                policy=VersionRef(id=policy.id, version=1),
                admission_id=admission.id,
                input=f"ADVANCED_{identifier}: Synthetic input; demonstrate {title}.",
            )
        )
    old = state.respond
    counts = {}

    def respond(body):
        messages = json.dumps(body["messages"])
        if "ADVANCED_" not in messages:
            return old(body)
        state.status, state.delay, state.parts = 200, 0, None
        counts[messages] = counts.get(messages, 0) + 1
        content = (
            "Incomplete fixture response"
            if "ADVANCED_H" in messages and counts[messages] % 2 == 1
            else "VALID: synthetic stage result; not a quality measurement."
        )
        if body.get("response_format", {}).get("type") in ("json_object", "json_schema"):
            content = json.dumps({"answer": content})
        state.result = wire(content=content)
        if body.get("stream"):
            state.parts = [
                sse({"content": content}),
                sse({}, "stop"),
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
    return (catalog, health_catalog), tuple(scenarios)
