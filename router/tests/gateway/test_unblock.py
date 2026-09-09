"""7B integration checks. Loopback server is synthetic, NOT live inference."""

import asyncio
import json
import socket
import threading
import time
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import pytest
from buildbox_router.api import create_app
from buildbox_router.auth import password_hash
from buildbox_router.composition import fixture_services
from buildbox_router.config import Settings
from buildbox_router.errors import DomainError
from buildbox_router.execution_composition import compose_execution
from buildbox_router.execution_contracts import (
    ApprovedEndpoint,
    ChatCompletionRequest,
    ExecutablePolicy,
    ResponseFormat,
    RouteAlias,
    RunAttempt,
    ToolDefinition,
    TransitionRequest,
    VariantRequest,
    VersionRef,
    WorkflowRunRequest,
    digest,
)
from buildbox_router.execution_jobs import QueuedWorkflows
from buildbox_router.execution_policy import variant
from buildbox_router.execution_storage import SandboxStorage, append
from buildbox_router.gateway.adapters import TargetAdapters
from buildbox_router.inference_transport import endpoint_address, exchange
from buildbox_router.provider_contracts import ProviderRequest
from buildbox_router.runtime_contracts import ApprovedBudget, RuntimeRegistry, WorkspaceRuntime
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text

from .conftest import ctx
from .test_http_adapters import hosted

_CONNECT = socket.socket.connect


def schema():
    return {
        "type": "object",
        "properties": {"category": {"type": "string"}},
        "required": ["category"],
        "additionalProperties": False,
    }


def tool():
    return ToolDefinition.model_validate(
        {
            "type": "function",
            "function": {"name": "classify", "parameters": schema(), "strict": True},
        }
    )


def wire(*, content="synthetic", calls=None):
    return {
        "model": "synthetic/test",
        "provider": "synthetic-provider",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content, "tool_calls": calls},
                "finish_reason": "tool_calls" if calls else "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cost": 0},
    }


def sse(delta=None, finish=None, usage=None):
    return (
        "data: "
        + json.dumps(
            {
                "model": "synthetic/test",
                "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}]
                if delta is not None or finish
                else [],
                "usage": usage,
            },
            ensure_ascii=False,
        )
        + "\n\n"
    ).encode()


@pytest.fixture
def loopback(rt, monkeypatch):
    # Explicit scoped exception to ordinary-test network denial. ONLY this
    # synthetic server's exact bound loopback port can be connected to.
    state = SimpleNamespace(parts=None, delay=0, seen=[], status=200, result=wire())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            state.seen.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(state.status)
            self.send_header(
                "Content-Type",
                "text/event-stream" if state.parts is not None else "application/json",
            )
            self.end_headers()
            try:
                for part in (
                    state.parts if state.parts is not None else [json.dumps(state.result).encode()]
                ):
                    if state.delay:
                        time.sleep(state.delay)
                    self.wfile.write(part)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_port

    def scoped(sock, address):
        assert address == ("127.0.0.1", port), "Unexpected test egress destination"
        return _CONNECT(sock, address)

    monkeypatch.setattr(socket.socket, "connect", scoped)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    hosted(rt)
    rt.target = rt.target.model_copy(update={"approved_endpoint_id": "fixture-loopback"})
    rt.credential = rt.credential.model_copy(
        update={"adapter_id": "openai_compatible", "secret_reference": None}
    )
    state.endpoint = ApprovedEndpoint(
        id="fixture-loopback",
        tenant_id="alice",
        url=f"http://127.0.0.1:{port}/v1/chat/completions",
        network="loopback",
        adapter_id="openai_compatible",
        credential_reference_id="credential",
        authorization_reference="software-test-only",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    rt.gateway.inference = TargetAdapters(
        lambda *_: pytest.fail("No credential permitted"), lambda *_: state.endpoint
    )
    state.registry = RuntimeRegistry(
        workspaces=(
            WorkspaceRuntime(
                tenant_id="alice",
                targets=(rt.target,),
                catalogs=(rt.catalog,),
                credentials=(rt.credential,),
                grants=(rt.grant,),
                admissions=(rt.admission,),
                endpoints=(state.endpoint,),
                budgets=(ApprovedBudget(id="budget", max_cost_micro_usd=1000),),
            ),
        )
    )
    yield state
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def collect(rt, request=None, context=None):
    async def run():
        return [
            v
            async for v in rt.gateway.stream(
                context or ctx(key=rt.key),
                request or rt.request.model_copy(update={"stream": True}),
            )
        ]

    return asyncio.run(run())


@pytest.mark.parametrize("split", [1, 2, 7, 31, 4096])
def test_real_loopback_incremental_utf8_and_coalesced_frames(rt, loopback, split):
    raw = (
        b": keepalive\n\n"
        + sse({"content": "héllo"})
        + sse({}, "stop")
        + sse(usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cost": 0})
        + b"data: [DONE]\n\n"
    )
    loopback.parts = [raw[n : n + split] for n in range(0, len(raw), split)]
    context = ctx(key=rt.key)
    events = collect(rt, context=context)
    assert events[0].choices[0].delta.content == "héllo"
    assert events[-1].choices[0].finish_reason == "stop"
    attempt = RunAttempt.model_validate_json(
        rt.store.latest("alice", "attempt", context.request_id)[1]
    )
    assert attempt.usage.actual_micro_usd == 0
    assert attempt.usage.tokens.total_tokens == 12
    assert "provider" not in loopback.seen[0]  # No OpenRouter extension on direct transport.


@pytest.mark.parametrize(
    "tail",
    [
        b"data: nope\n\n",
        b'data: {"error":{"code":500,"message":"private upstream error"}}\n\n',
        b"data: [DONE]\n\n",
    ],
)
def test_stream_malformed_midstream_errors_and_truncation(rt, loopback, tail):
    loopback.parts = [sse({"content": "first"}), tail]
    result = collect(rt)
    assert result[0].choices[0].delta.content == "first"
    assert result[-1].error.code == "partial_failure"
    assert "private upstream" not in result[-1].model_dump_json()
    assert len(loopback.seen) == 1


def test_real_stream_cancellation_closes_and_holds_unknown(rt, loopback):
    loopback.parts = [
        sse({"content": "first"}),
        sse({"content": "next"}),
        sse({}, "stop"),
        b"data: [DONE]\n\n",
    ]
    context = ctx(key=rt.key)

    async def run():
        source = rt.gateway.stream(context, rt.request.model_copy(update={"stream": True}))
        first = await anext(source)
        assert first.choices[0].delta.content == "first"
        await source.aclose()

    asyncio.run(run())
    assert rt.store.request_state("alice", context.request_id) == "uncertain"
    assert (
        RunAttempt.model_validate_json(
            rt.store.read("alice", "attempt", context.request_id)
        ).usage.actual_micro_usd
        is None
    )


def test_transport_timeout_before_any_output(rt, loopback):
    loopback.parts = [sse({"content": "late"})]
    loopback.delay = 0.2

    async def run():
        return [
            v
            async for v in exchange(
                loopback.endpoint,
                ProviderRequest(
                    model="synthetic/test", messages=rt.request.messages, max_tokens=10, stream=True
                ),
                None,
                lambda: None,
                0.02,
            )
        ]

    with pytest.raises(TimeoutError):
        asyncio.run(run())


def test_tool_call_network_stream_and_roundtrip_never_executes(rt, loopback):
    request = ChatCompletionRequest.model_validate(
        rt.request.model_dump()
        | {"stream": True, "tools": [tool().model_dump()], "tool_choice": "required"}
    )
    loopback.parts = [
        sse(
            {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call-synthetic",
                        "type": "function",
                        "function": {"name": "classify", "arguments": '{"cat'},
                    }
                ]
            }
        ),
        sse({"tool_calls": [{"index": 0, "function": {"arguments": 'egory":"ok"}'}}]}),
        sse({}, "tool_calls"),
        b"data: [DONE]\n\n",
    ]
    events = collect(rt, request)
    assert events[0].choices[0].delta.tool_calls[0].id == "call-synthetic"
    assert events[-1].choices[0].finish_reason == "tool_calls"
    calls = [
        {
            "id": "call-synthetic",
            "type": "function",
            "function": {"name": "classify", "arguments": '{"category":"ok"}'},
        }
    ]
    follow = ChatCompletionRequest.model_validate(
        rt.request.model_dump()
        | {
            "tools": [tool().model_dump()],
            "messages": [
                {"role": "user", "content": "classify"},
                {"role": "assistant", "tool_calls": calls},
                {"role": "tool", "tool_call_id": "call-synthetic", "content": "synthetic result"},
            ],
        }
    )
    loopback.parts = None
    result = asyncio.run(rt.gateway.complete(ctx(key=rt.key), follow))
    assert result.choices[0].message.content == "synthetic"
    assert loopback.seen[-1]["messages"][-1]["tool_call_id"] == "call-synthetic"


@pytest.mark.parametrize("valid", [True, False])
def test_strict_json_validated_before_delivery(rt, loopback, valid):
    loopback.result = wire(content='{"category":"ok"}' if valid else '{"other":4}')
    request = ChatCompletionRequest.model_validate(
        rt.request.model_dump()
        | {
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "category", "strict": True, "schema": schema()},
            }
        }
    )
    if valid:
        result = asyncio.run(rt.gateway.complete(ctx(key=rt.key), request))
        assert json.loads(result.choices[0].message.content) == {"category": "ok"}
    else:
        with pytest.raises(DomainError):
            asyncio.run(rt.gateway.complete(ctx(key=rt.key), request))


@pytest.mark.parametrize(
    "extra",
    [
        {"n": 1},
        {"top_p": 0.9},
        {"stream_options": {"include_usage": True}},
        {"parallel_tool_calls": True},
        {"user": "private"},
        {"response_format": {"type": "json_object"}, "stream": True},
        {"tools": [tool().model_dump()], "response_format": {"type": "json_object"}},
    ],
)
def test_unsupported_combinations_preflight_no_upstream(rt, loopback, extra):
    with pytest.raises(ValidationError):
        ChatCompletionRequest.model_validate(rt.request.model_dump() | extra)
    assert not loopback.seen


def test_provider_capability_mismatch_has_no_dispatch(rt, loopback):
    rt.target = rt.target.model_copy(
        update={
            "endpoint": rt.target.endpoint.model_copy(
                update={"supported_parameters": rt.fact(("max_tokens",))}
            )
        }
    )
    request = rt.request.model_copy(update={"response_format": ResponseFormat(type="json_object")})
    with pytest.raises(DomainError):
        asyncio.run(rt.gateway.complete(ctx(key=rt.key), request))
    assert not loopback.seen


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/v1/chat/completions",
        "http://169.254.169.254:80/v1/chat/completions",
        "http://127.0.0.1:8000/secret",
        "http://a:b@127.0.0.1:8000/v1/chat/completions",
        "http://127.0.0.1:8000/v1/chat/completions?key=hidden",
    ],
)
def test_approved_endpoint_policy_rejects_unsafe_targets(loopback, url):
    with pytest.raises(ValueError):
        endpoint_address(loopback.endpoint.model_copy(update={"url": url}))


def test_redirect_is_not_followed(rt, loopback):
    loopback.status = 302
    with pytest.raises(DomainError):
        asyncio.run(rt.gateway.complete(ctx(key=rt.key), rt.request))
    assert len(loopback.seen) == 1


@pytest.mark.parametrize("mode", ["quality", "balanced", "cost_conscious"])
def test_policy_variants_are_draft_material_not_active_mutation(rt, mode):
    original = digest(rt.policy)
    result = variant(
        rt.policy,
        rt.catalog,
        VariantRequest(id="variant-" + mode, mode=mode),
        fixture_services(rt.store).selector,
    )
    assert result.variant.mode == mode and not result.variant.quality_validated
    assert result.quality == "untested_provisional"
    assert result.version == 1 and result.id != rt.policy.id
    assert digest(rt.store.policy("alice", rt.ref).policy) == original
    assert rt.store.alias("alice", "test-alias") == rt.alias


def test_product_auth_to_queue_restart_worker_to_persisted_runtime(rt, loopback, tmp_path):
    services = fixture_services(rt.store)
    execution = compose_execution(
        rt.store, loopback.registry, services.selector, retention_seconds=60
    )
    authfile = tmp_path / "synthetic-auth.json"
    salt = "0" * 32
    authfile.write_text(
        json.dumps(
            [
                {
                    "username": "fixture",
                    "owner": "alice",
                    "salt": salt,
                    "password_hash": password_hash("synthetic-test-password", salt),
                }
            ]
        )
    )
    settings = Settings(identity_mode="shared", auth_file=str(authfile))
    app = create_app(settings, services, execution, rt.store)
    with TestClient(app) as client:
        assert client.get("/api/studio/runs").status_code == 401
        client.auth = ("fixture", "synthetic-test-password")
        assert client.get("/api/studio/runtime").json()["mode"] == "synthetic_test"
        response = client.post(
            "/api/sandbox/runs",
            json={
                "policy": rt.ref.model_dump(),
                "inputs": {"document": "   synthetic document   "},
            },
            headers={"Idempotency-Key": "7b-workflow-synthetic"},
        )
        assert response.status_code == 202, response.text
        run = response.json()
        assert run["status"] == "queued" and not loopback.seen
        # New composition/session claims durable state, using the same worker operation.
        restarted = compose_execution(
            SandboxStorage(rt.store.engine, offline_contract_test=True),
            loopback.registry,
            services.selector,
            retention_seconds=60,
        )
        assert isinstance(restarted.workflows, QueuedWorkflows)
        from buildbox_router.worker import run_once

        assert run_once(services, execution=restarted)
        assert not run_once(services, execution=restarted)
        result = client.get("/api/sandbox/runs/" + run["id"]).json()
        assert result["status"] == "awaiting_approval", result
        assert loopback.seen[0]["messages"][0]["content"].endswith("synthetic document")
        attempts = client.get("/api/studio/runs/" + run["id"] + "/attempts").json()
        assert len(attempts) == 1 and attempts[0]["usage"]["actual_micro_usd"] == 0
        assert client.get("/api/studio/traces/" + attempts[0]["id"]).status_code == 200
        assert client.get("/api/studio/runs").json()[0]["id"] == run["id"]
        assert (
            client.post(
                "/api/sandbox/runs",
                json={
                    "policy": rt.ref.model_dump(),
                    "inputs": {"document": "   synthetic document   "},
                },
                headers={"Idempotency-Key": "7b-workflow-synthetic"},
            ).json()["id"]
            == run["id"]
        )
        assert len(loopback.seen) == 1
        issued = client.post(
            "/api/studio/keys",
            json={
                "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
                "scopes": ["models:read", "chat:complete"],
                "alias_ids": ["test-alias"],
                "max_cost_micro_usd": 100,
            },
        ).json()
        bearer = {"Authorization": "Bearer " + issued["secret"]}
        client.auth = None
        assert client.get("/v1/models", headers=bearer).status_code == 200
        assert (
            client.post(
                "/v1/chat/completions", headers=bearer, json=rt.request.model_dump()
            ).status_code
            == 200
        )
        client.auth = ("fixture", "synthetic-test-password")
        assert (
            client.post(
                "/api/studio/keys/" + issued["metadata"]["id"] + "/revoke", json={}
            ).status_code
            == 200
        )
        client.auth = None
        assert client.get("/v1/models", headers=bearer).status_code == 401
    with pytest.raises(DomainError):
        rt.store.read("bob", "run", run["id"])
    assert issued["secret"] not in "".join(rt.store.records("alice", "application_key"))


def test_expired_worker_lease_is_uncertain_not_replayed(rt):
    queued = QueuedWorkflows(rt.runner)
    context = ctx()
    value = WorkflowRunRequest(policy=rt.ref, inputs={"document": "sample"})
    run = asyncio.run(queued.submit(context, value))
    assert rt.store.claim_runtime()
    with rt.store.engine.begin() as c:
        c.execute(text("UPDATE runtime_queue SET lease_until=0"))
    assert rt.store.claim_runtime() is None
    assert rt.store.request_state("alice", run.id) == "uncertain"
    assert not rt.inference.calls


def enable_fallback(rt):
    hosted(rt)
    other = rt.target.model_copy(
        update={
            "configuration": rt.target.configuration.model_copy(update={"id": "fixture-fallback"})
        }
    )
    rt.catalog = rt.catalog.model_copy(
        update={"configurations": rt.catalog.configurations + (other.configuration,)}
    )
    rt.authority.target = lambda tenant, identifier: (
        other if identifier == other.configuration.id else rt.target
    )
    rt.grant = rt.grant.model_copy(
        update={"configuration_ids": (rt.target.configuration.id, other.configuration.id)}
    )
    stages = tuple(
        s.model_copy(
            update={
                "fallback_configuration_ids": (other.configuration.id,),
                "budget": s.budget.model_copy(update={"max_attempts": 2, "max_model_calls": 2}),
            }
        )
        if s.configuration_id
        else s
        for s in rt.policy.stages
    )
    policy = ExecutablePolicy.model_validate(
        rt.policy.model_dump()
        | {
            "id": "fallback-policy",
            "stages": stages,
            "budget": rt.policy.budget.model_copy(update={"max_model_calls": 2}),
        }
    )
    ref = VersionRef(id=policy.id, version=1)
    admission = rt.admission.model_copy(
        update={
            "id": "fallback-admission",
            "policy": ref,
            "policy_digest": digest(policy),
            "configuration_ids": (rt.target.configuration.id, other.configuration.id),
        }
    )
    rt.store._append_policy("alice", policy)
    with rt.store.engine.begin() as conn:
        append(conn, "alice", "admission", admission.id, 1, admission)
    rt.store.transition(
        "alice",
        ref,
        TransitionRequest(expected_sequence=1, status="sandbox_enabled", admission_id=admission.id),
    )
    rt.store.create_alias(
        "alice",
        RouteAlias(
            id="fallback-alias",
            policy=ref,
            node_id="classify",
            configuration_id=rt.target.configuration.id,
            created_at=datetime.now(UTC),
        ),
    )
    key, _ = rt.keys.issue(
        ctx(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        scopes=("models:read", "chat:complete"),
        aliases=("fallback-alias",),
        max_cost_micro_usd=1000,
    )
    return rt.request.model_copy(update={"model": "fallback-alias"}), ctx(key=key)


@pytest.mark.parametrize("committed", [False, True])
def test_fallback_only_before_stream_commit_all_attempts_persist(rt, committed):
    request, context = enable_fallback(rt)
    calls = []

    async def stream(context, call):
        from buildbox_router.execution_contracts import ChatCompletionChunk

        calls.append(call.target.configuration.id)

        def chunk(content=None, finish=None):
            return ChatCompletionChunk.model_validate(
                {
                    "id": context.request_id,
                    "created": 0,
                    "model": request.model,
                    "choices": [
                        {"index": 0, "delta": {"content": content}, "finish_reason": finish}
                    ],
                }
            )

        if call.target.configuration.id == "fixture-small-local":
            if committed:
                yield chunk("first")
            raise TimeoutError("synthetic failure")
        yield chunk("fallback")
        yield chunk(finish="stop")

    rt.inference.stream = stream
    result = collect(rt, request.model_copy(update={"stream": True}), context)
    if committed:
        assert calls == ["fixture-small-local"] and result[-1].error.code == "partial_failure"
    else:
        assert calls == ["fixture-small-local", "fixture-fallback"]
        assert result[0].choices[0].delta.content == "fallback"
        assert result[-1].choices[0].finish_reason == "stop"
    attempts = [RunAttempt.model_validate_json(v) for v in rt.store.records("alice", "attempt")]
    assert sorted(a.attempt for a in attempts) == ([1] if committed else [1, 2])
    assert all(a.usage.actual_micro_usd is None for a in attempts)


def test_unknown_fallback_capability_blocks_entire_request(rt):
    request, context = enable_fallback(rt)
    resolve = rt.authority.target
    rt.authority.target = lambda t, c: (
        resolve(t, c).model_copy(
            update={
                "endpoint": resolve(t, c).endpoint.model_copy(
                    update={
                        "supported_parameters": rt.fact(()).model_copy(
                            update={"value": None, "unknown_reason": "No capability evidence"}
                        )
                    }
                )
            }
        )
        if c == "fixture-fallback"
        else resolve(t, c)
    )
    with pytest.raises(DomainError):
        asyncio.run(rt.gateway.complete(context, request))
    assert not rt.inference.calls


def test_multiturn_fallback_alias_is_rejected_without_implicit_repin(rt):
    request, context = enable_fallback(rt)
    request = ChatCompletionRequest.model_validate(
        request.model_dump()
        | {
            "messages": [
                {"role": "user", "content": "first"},
                {"role": "assistant", "content": "prior answer"},
                {"role": "user", "content": "continue"},
            ]
        }
    )
    with pytest.raises(DomainError):
        asyncio.run(rt.gateway.complete(context, request))
    assert not rt.inference.calls


def test_legacy_policy_digest_and_revision_three_migration(tmp_path):
    import hashlib
    from pathlib import Path

    from buildbox_router.migrations import migrate, revision_one, revision_three, revision_two
    from buildbox_router.storage import engine_for

    # Original Prompt 7 JSON without new additive defaults retains its signed digest.
    raw = json.loads(
        (Path(__file__).parents[2] / "contract-fixtures/sandbox-policy-v2.json").read_text()
    )

    def old(value):
        if isinstance(value, dict):
            return {
                k: old(v)
                for k, v in value.items()
                if k
                not in {
                    "max_attempts",
                    "variant",
                    "fallback_configuration_ids",
                    "route_requirements",
                    "response_format",
                }
            }
        if isinstance(value, list):
            return [old(v) for v in value]
        return value

    legacy = old(raw)
    assert (
        digest(ExecutablePolicy.model_validate(legacy))
        == hashlib.sha256(
            json.dumps(legacy, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    engine = engine_for(Settings(database_url=f"sqlite:///{tmp_path}/upgrade.db"))
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE schema_revisions(version INTEGER PRIMARY KEY)"))
        revision_one(conn, "sqlite")
        revision_two(conn)
        revision_three(conn, "sqlite")
        conn.execute(text("INSERT INTO schema_revisions VALUES(1),(2),(3)"))
        conn.execute(
            text(
                "INSERT INTO sandbox_records(owner,kind,id,version,payload) VALUES('alice','policy','legacy',1,:payload)"
            ),
            {"payload": json.dumps(legacy)},
        )
    migrate(engine)
    migrate(engine)
    store = SandboxStorage(engine)
    store.check_revision()
    assert json.loads(store.read("alice", "policy", "legacy")) == legacy
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM runtime_queue")).scalar_one() == 0
    engine.dispose()


def test_comparison_uses_worker_outputs_actual_attempts_and_budget(rt, loopback):
    from buildbox_router.execution_contracts import ComparisonRequest, ImportedSample

    refs = []
    for name in ("compare-a", "compare-b"):
        workflow = rt.policy.workflow.model_copy(
            update={"nodes": tuple(n for n in rt.policy.workflow.nodes if n.id != "review")}
        )
        policy = ExecutablePolicy.model_validate(
            rt.policy.model_dump()
            | {
                "id": name,
                "workflow": workflow,
                "stages": tuple(s for s in rt.policy.stages if s.node_id != "review"),
            }
        )
        ref = VersionRef(id=name, version=1)
        refs.append(ref)
        admission = rt.admission.model_copy(
            update={"id": name + "-admit", "policy": ref, "policy_digest": digest(policy)}
        )
        rt.store._append_policy("alice", policy)
        with rt.store.engine.begin() as conn:
            append(conn, "alice", "admission", admission.id, 1, admission)
        rt.store.transition(
            "alice",
            ref,
            TransitionRequest(
                expected_sequence=1, status="sandbox_enabled", admission_id=admission.id
            ),
        )
    sample = ImportedSample(
        id="comparison-sample",
        kind="sample",
        inputs={"document": "  sample  "},
        source_label="Synthetic only",
        imported_at=datetime.now(UTC),
        data_class="synthetic",
        processing="approved_hosted",
        retention_days=1,
    )
    rt.store.import_sample("alice", sample)
    runtime = compose_execution(
        rt.store, loopback.registry, fixture_services(rt.store).selector, retention_seconds=60
    )
    value = ComparisonRequest(
        sample_ids=(sample.id,),
        policies=tuple(refs),
        budget=rt.policy.budget.model_copy(update={"max_model_calls": 2}),
    )
    context = ctx()
    pending = asyncio.run(runtime.comparisons.submit(context, value))
    assert all(c.status == "not_run" for c in pending.cells) and not loopback.seen
    from buildbox_router.worker import run_once

    assert run_once(fixture_services(rt.store), execution=runtime)
    assert run_once(fixture_services(rt.store), execution=runtime)
    result = asyncio.run(runtime.comparisons.get(ctx(), pending.id))
    assert all(c.status == "completed" and c.output_reference for c in result.cells)
    assert all(
        len(c.attempt_usages) == 1 and c.attempt_usages[0].actual_micro_usd == 0
        for c in result.cells
    )
    assert all(c.usage is None for c in result.cells)  # Never a fabricated aggregate reservation.
    assert result.quality_claim == "exploratory_not_quality_validation"
    assert len(loopback.seen) == 2
    with pytest.raises(DomainError):
        asyncio.run(
            runtime.comparisons.submit(ctx(), value.model_copy(update={"budget": rt.policy.budget}))
        )
    assert len(loopback.seen) == 2


def test_live_registry_cannot_dispatch_from_fixture_mode():
    with pytest.raises(ValidationError):
        Settings(
            runtime_registry_file="operator-registry.json",
            identity_mode="shared",
            auth_file="operator-users.json",
        )


def test_registry_budget_replacement_is_not_silently_accepted(rt, loopback):
    workspace = loopback.registry.workspaces[0]
    registry = loopback.registry.model_copy(
        update={
            "workspaces": (
                workspace.model_copy(
                    update={"budgets": (ApprovedBudget(id="budget", max_cost_micro_usd=1),)}
                ),
            )
        }
    )
    with pytest.raises(ValueError):
        compose_execution(
            rt.store, registry, fixture_services(rt.store).selector, retention_seconds=60
        )
    assert rt.store.budget_cap("alice", "budget") == 1000


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1e999", '{"x":1,"x":2}'])
def test_structured_parser_rejects_nonfinite_and_duplicate_keys(value):
    from buildbox_router.json_contracts import parse_json

    with pytest.raises(ValueError):
        parse_json(value)
