import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from buildbox_router.contracts import Fact
from buildbox_router.errors import DomainError
from buildbox_router.execution_contracts import (
    ChatCompletionRequest,
    GatewayError,
    RunAttempt,
    TransitionRequest,
    WorkflowRunRequest,
)
from buildbox_router.gateway.adapters import SSEDecoder, TargetAdapters, actual_cost, usage
from buildbox_router.gateway.keys import ApplicationKeys
from buildbox_router.gateway.runner import SampleTools, WorkflowRunner, render
from buildbox_router.gateway.service import Gateway
from pydantic import ValidationError
from sqlalchemy import text

from .conftest import ctx


def run(awaitable):
    return asyncio.run(awaitable)


def test_complete_pinned_prompt_trace_and_no_default_content_retention(rt):
    context = ctx(key=rt.key)
    result = run(rt.gateway.complete(context, rt.request))
    assert result.model == "test-alias"
    assert rt.inference.calls[0].messages.messages[0].content == rt.policy.prompts[0].template
    trace = rt.store.trace("alice", context.request_id)
    assert trace.policy == rt.ref and trace.served_model.value is None
    with rt.store.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM sandbox_payloads")).scalar() == 0
    assert "Synthetic document" not in trace.model_dump_json()


def test_duplicate_and_restart_no_redispatch(rt):
    context = ctx(key=rt.key)
    rt.gateway.retain_seconds = 60
    first = run(rt.gateway.complete(context, rt.request))
    second = Gateway(rt.authority, rt.inference, ApplicationKeys(rt.store), retain_seconds=60)
    assert run(second.complete(replace(context, request_id="second-request"), rt.request)) == first
    assert len(rt.inference.calls) == 1
    with pytest.raises(DomainError, match="different content"):
        run(second.complete(context, rt.request.model_copy(update={"max_tokens": 31})))


def test_key_verifier_expiry_revoke_wrong_secret_and_scope(rt):
    with pytest.raises(DomainError):
        run(
            rt.keys.authenticate(
                rt.raw[:-1] + ("a" if rt.raw[-1] != "a" else "b"), datetime.now(UTC)
            )
        )
    with pytest.raises(DomainError):
        run(rt.keys.authenticate(rt.raw, datetime.now(UTC) + timedelta(days=1)))
    _, verifier = rt.store.key_record("alice", rt.key.id)
    assert rt.raw not in verifier
    run(rt.keys.revoke(ctx(), rt.key.id))
    with pytest.raises(DomainError):
        run(ApplicationKeys(rt.store).authenticate(rt.raw, datetime.now(UTC)))
    with pytest.raises(DomainError):
        run(rt.gateway.complete(ctx(key=rt.key), rt.request))
    assert not rt.inference.calls


@pytest.mark.parametrize("name", ["foreign-alias", "fixture-small-local", "openrouter-auto"])
def test_alias_access_before_resolution(rt, name):
    with pytest.raises(DomainError, match="cannot access"):
        run(rt.gateway.complete(ctx(key=rt.key), rt.request.model_copy(update={"model": name})))
    assert not rt.inference.calls


def test_models_only_current_key_allowed_usable_aliases(rt):
    assert [v.id for v in run(rt.gateway.models(ctx(key=rt.key))).data] == [rt.alias.id]
    rt.store.transition("alice", rt.ref, TransitionRequest(expected_sequence=2, status="disabled"))
    assert not run(rt.gateway.models(ctx(key=rt.key))).data


@pytest.mark.parametrize(
    "field,value",
    [
        ("tools", []),
        ("tool_choice", "auto"),
        (
            "response_format",
            {"type": "json_schema", "json_schema": {"name": "x", "schema": {"type": "object"}}},
        ),
        ("n", 2),
        ("max_completion_tokens", 10),
        ("provider", {}),
    ],
)
def test_unsupported_contract_rejected_before_transport(rt, field, value):
    with pytest.raises(ValidationError):
        ChatCompletionRequest.model_validate(rt.request.model_dump() | {field: value})
    assert not rt.inference.calls


@pytest.mark.parametrize(
    "change", ["context", "parameters", "privacy", "digest", "grant", "credential", "catalog"]
)
def test_fail_closed_endpoint_and_authority(rt, change):
    if change in ("context", "parameters", "privacy", "digest"):
        field = {
            "context": "context_tokens",
            "parameters": "supported_parameters",
            "privacy": "privacy",
            "digest": "weights_digest",
        }[change]
        local = rt.target.local.model_copy(
            update={field: Fact(unknown_reason="Not verified", provenance=rt.fact(1).provenance)}
        )
        rt.target = rt.target.model_copy(update={"local": local})
    elif change == "grant":
        rt.grant = rt.grant.model_copy(update={"allowed_data_classes": ("synthetic",)})
    elif change == "credential":
        rt.credential = rt.credential.model_copy(update={"tenant_id": "bob"})
    else:
        rt.target = rt.target.model_copy(update={"catalog_id": "different-catalog"})
    with pytest.raises(DomainError):
        run(rt.gateway.complete(ctx(key=rt.key), rt.request))
    assert not rt.inference.calls


def test_unknown_usage_timeout_holds_and_sanitization(rt):
    context = ctx(key=rt.key)
    rt.inference.error = TimeoutError("DO-NOT-STORE private provider credential")
    with pytest.raises(DomainError):
        run(rt.gateway.complete(context, rt.request))
    _, raw = rt.store.latest("alice", "attempt", context.request_id)
    attempt = RunAttempt.model_validate_json(raw)
    assert attempt.usage.state == "uncertain" and attempt.usage.actual_micro_usd is None
    assert "DO-NOT-STORE" not in raw
    with pytest.raises(DomainError):
        run(rt.gateway.complete(context, rt.request))
    assert len(rt.inference.calls) == 1


def test_cancellation_no_dispatch(rt):
    def stop():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        run(rt.gateway.complete(ctx(key=rt.key, check_cancelled=stop), rt.request))
    assert not rt.inference.calls


def test_concurrent_caps_are_atomic_and_unknown_not_refunded(rt):
    rt.store.provision_budget("alice", "tiny-budget", 10)

    def reserve(i):
        try:
            rt.store.reserve("alice", "tiny-budget", f"hold-{i}", f"req-{i}", 6)
            rt.store.reconcile("alice", f"hold-{i}", None)
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(reserve, range(4))) == 1


def test_rate_cap_survives_new_key_service(rt):
    rt.keys.requests_per_minute = 1
    run(rt.gateway.complete(ctx(key=rt.key), rt.request))
    rt.gateway.keys = ApplicationKeys(rt.store, requests_per_minute=1)
    with pytest.raises(DomainError):
        run(rt.gateway.complete(ctx(key=rt.key), rt.request))
    assert len(rt.inference.calls) == 1


def test_utf8_fragmentation_comments_usage_and_terminal():
    data = ': ping\r\ndata: {"text":"☀"}\r\n\r\ndata: {"choices":[],"usage":{"total_tokens":3}}\n\ndata: [DONE]\n\n'.encode()
    decoder = SSEDecoder()
    result = []
    for b in data:
        result.extend(decoder.feed(bytes([b])))
    decoder.finish()
    assert result[0] == {"text": "☀"} and result[-1] == "[DONE]"


@pytest.mark.parametrize(
    "payload",
    [
        b'data: {"error":{"message":"private"}}\n\n',
        b"data: {bad}\n\n",
        b"data: [DONE]\n\ndata: {}\n\n",
        b'data: {"x":"\xff"}\n\n',
    ],
)
def test_sse_failed_200_malformed_and_after_done(payload):
    with pytest.raises((ValueError, UnicodeError)):
        SSEDecoder().feed(payload)


def test_sse_truncation_and_bounds():
    decoder = SSEDecoder()
    decoder.feed(b'data: {"x":1}\n\n')
    with pytest.raises(ValueError):
        decoder.finish()
    with pytest.raises(ValueError):
        SSEDecoder().feed(b"x" * 65537)


def frames(text="first"):
    return {"choices": [{"index": 0, "delta": {"content": text}, "finish_reason": None}]}


def test_stream_is_incremental_and_post_commit_error_explicit(rt):
    from .test_http_adapters import hosted

    hosted(rt)
    rt.inference.frames = [frames(), TimeoutError("private error")]

    async def collect():
        return [
            c
            async for c in rt.gateway.stream(
                ctx(key=rt.key), rt.request.model_copy(update={"stream": True})
            )
        ]

    result = run(collect())
    assert result[0].choices[0].delta.content == "first"
    assert isinstance(result[-1], GatewayError) and "Partial failure" in result[-1].error.message
    assert len(rt.inference.calls) == 1


def test_stream_terminal_usage_pending(rt):
    from .test_http_adapters import hosted

    hosted(rt)
    rt.inference.frames = [
        frames(),
        {
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    ]
    context = ctx(key=rt.key)

    async def collect():
        return [
            c
            async for c in rt.gateway.stream(
                context, rt.request.model_copy(update={"stream": True})
            )
        ]

    result = run(collect())
    assert result[-1].choices[0].finish_reason == "stop"
    attempt = RunAttempt.model_validate_json(
        rt.store.latest("alice", "attempt", context.request_id)[1]
    )
    assert attempt.usage.actual_micro_usd is None and attempt.usage.tokens.total_tokens == 2


def test_prompt_literal_not_recursive_and_typed(rt):
    prompt = rt.policy.prompts[0]
    assert render(prompt, {"text": "{{text}}"}).endswith("{{text}}")
    with pytest.raises(DomainError):
        render(prompt, {"text": 3})


def test_dag_propagation_human_pause_and_reload(rt):
    context = ctx()
    value = WorkflowRunRequest(policy=rt.ref, inputs={"document": "   fixture text   "})
    result = run(rt.runner.submit(context, value))
    assert result.status == "awaiting_approval"
    assert rt.inference.calls[0].messages.messages[0].content.endswith("fixture text")
    output = rt.store.output("alice", result.output_reference)
    assert output.value == {"result": "SYNTHETIC_CATEGORY"}
    restarted = WorkflowRunner(rt.gateway, SampleTools({}), retain_seconds=60)
    assert run(restarted.submit(context, value)).status == "awaiting_approval"
    assert len(rt.inference.calls) == 1
    with pytest.raises(DomainError):
        run(restarted.get(ctx("bob"), result.id))

    async def read():
        return [e async for e in restarted.events(ctx(), result.id, 2)]

    events = run(read())
    assert [e.sequence for e in events] == list(range(3, 3 + len(events)))


def test_tool_allowlist_no_declared_business_execution(rt):
    tools = SampleTools({("alice", "sample-lookup-demo"): {"a": "synthetic result"}})
    budget = rt.policy.budget.model_copy(update={"max_tool_calls": 1})
    assert run(tools.dispatch(ctx(), "sample-lookup-demo", {"key": "a"}, budget)) == {
        "result": "synthetic result"
    }
    for tenant, tool in [("alice", "email"), ("bob", "sample-lookup-demo"), ("alice", "terminal")]:
        with pytest.raises(DomainError):
            run(tools.dispatch(ctx(tenant), tool, {"key": "a"}, budget))


def test_actual_price_and_usage_unknown_are_not_zero():
    assert actual_cost({}) is None and usage({}) is None
    assert actual_cost({"cost": 0}) == 0
    assert actual_cost({"cost": 0.0000001}) == 1
    assert actual_cost({"cost": float("nan")}) is None


def test_local_adapter_uses_fixed_transport_digest_and_no_pull(rt, monkeypatch):
    from buildbox_router.gateway import adapters

    calls = []

    def local(path, value, check):
        calls.append((path, value))
        check()
        if path == "/api/tags":
            return {"models": [{"name": "synthetic:fixture", "digest": "fixture-digest"}]}
        return {
            "model": "synthetic:fixture",
            "done": True,
            "done_reason": "stop",
            "message": {"content": "recorded output"},
            "prompt_eval_count": 2,
            "eval_count": 1,
        }

    monkeypatch.setattr(adapters, "local_request", local)
    rt.gateway.inference = TargetAdapters(
        lambda tenant, ref: pytest.fail("Local must not resolve provider key")
    )
    assert (
        run(rt.gateway.complete(ctx(key=rt.key), rt.request)).choices[0].message.content
        == "recorded output"
    )
    assert [c[0] for c in calls] == ["/api/tags", "/api/chat"]


def test_no_buffered_streaming_adapter(rt):
    rt.gateway.streaming_enabled = False
    rt.gateway.inference = TargetAdapters(
        lambda *_: pytest.fail("No credentials for unsupported stream")
    )

    async def collect():
        return [
            c
            async for c in rt.gateway.stream(
                ctx(key=rt.key), rt.request.model_copy(update={"stream": True})
            )
        ]

    with pytest.raises(DomainError, match="no upstream work"):
        run(collect())
