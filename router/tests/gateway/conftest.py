import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from buildbox_router.composition import fixture_services
from buildbox_router.contracts import Fact, Provenance
from buildbox_router.execution_contracts import (
    ChatCompletion,
    ChatCompletionChunk,
    ChatCompletionRequest,
    CompletionChoice,
    CompletionMessage,
    CompletionUsage,
    ExecutablePolicy,
    LocalDeployment,
    ProviderCredentialReference,
    RouteAlias,
    RuntimeGrant,
    SandboxAdmission,
    TargetConfiguration,
    TransitionRequest,
    VersionRef,
    digest,
)
from buildbox_router.execution_ports import InferenceResult, RequestContext
from buildbox_router.execution_storage import SandboxStorage, append
from buildbox_router.gateway.keys import ApplicationKeys
from buildbox_router.gateway.preflight import Authority
from buildbox_router.gateway.runner import SampleTools, WorkflowRunner
from buildbox_router.gateway.service import Gateway


def ctx(tenant="alice", key=None, **changes):
    identifier = uuid4().hex
    return replace(
        RequestContext(
            tenant,
            key.id if key else tenant,
            identifier,
            identifier,
            datetime.now(UTC) + timedelta(seconds=120),
            lambda: None,
            key,
        ),
        **changes,
    )


class RecordedInference:
    """Synthetic transport only. No real model quality/provider claim."""

    def __init__(self):
        self.calls = []
        self.error = None
        self.frames = []
        self.actual = 0
        self.after_call = lambda: None

    async def complete(self, context, call):
        self.calls.append(call)
        self.after_call()
        if self.error:
            raise self.error
        tokens = CompletionUsage(prompt_tokens=10, completion_tokens=1, total_tokens=11)
        result = ChatCompletion(
            id=context.request_id,
            created=0,
            model=call.messages.model,
            choices=(
                CompletionChoice(
                    message=CompletionMessage(content="SYNTHETIC_CATEGORY"), finish_reason="stop"
                ),
            ),
            usage=tokens,
        )
        return InferenceResult(result, self.actual, tokens, call.trace)

    async def stream(self, context, call):
        self.calls.append(call)
        for frame in self.frames:
            if isinstance(frame, BaseException):
                raise frame
            yield ChatCompletionChunk.model_validate(
                {"id": context.request_id, "created": 0, "model": call.messages.model, **frame}
            )


@pytest.fixture
def rt(storage):
    store = SandboxStorage(storage.engine, offline_contract_test=True)
    policy = ExecutablePolicy.model_validate_json(
        (Path(__file__).parents[2] / "contract-fixtures/sandbox-policy-v2.json").read_text()
    )
    ref = VersionRef(id=policy.id, version=policy.version)
    p = Provenance(
        kind="synthetic", source="Runtime software fixture ONLY", evidence_ids=("fixture-facts",)
    )

    def fact(value):
        return Fact(value=value, provenance=p)

    admission = SandboxAdmission(
        id="admission",
        tenant_id="alice",
        policy=ref,
        policy_digest=digest(policy),
        configuration_ids=("fixture-small-local",),
        credential_reference_ids=("credential",),
        authorization_reference="synthetic-approval",
        budget_reference="budget",
        privacy=fact(True),
        license_policy=fact(True),
        weights_access=fact(True),
        capabilities=fact(True),
        spending=fact(True),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    store._append_policy("alice", policy)
    with store.engine.begin() as connection:
        append(connection, "alice", "admission", admission.id, 1, admission)
    store.transition(
        "alice",
        ref,
        TransitionRequest(expected_sequence=1, status="sandbox_enabled", admission_id=admission.id),
    )
    alias = RouteAlias(
        id="test-alias",
        policy=ref,
        node_id="classify",
        configuration_id="fixture-small-local",
        created_at=datetime.now(UTC),
    )
    store.create_alias("alice", alias)
    services = fixture_services(storage)
    catalog = services.catalog.snapshot()
    target = TargetConfiguration(
        configuration=catalog.configurations[0],
        catalog_id=catalog.id,
        local=LocalDeployment(
            model_tag="synthetic:fixture",
            weights_digest=fact("fixture-digest"),
            supported_parameters=fact(("max_tokens", "temperature")),
            context_tokens=fact(4096),
            max_output_tokens=fact(128),
            privacy=fact("local_only"),
        ),
        limitations=("SYNTHETIC; no real model",),
    )
    credential = ProviderCredentialReference(
        id="credential",
        tenant_id="alice",
        adapter_id="local_ollama",
        approval_reference="synthetic-approval",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    grant = RuntimeGrant(
        id="grant",
        tenant_id="alice",
        configuration_ids=(target.configuration.id,),
        credential_reference_ids=(credential.id,),
        allowed_data_classes=("synthetic", "tenant_private"),
        budget_reference="budget",
        permission_reference="synthetic-approval",
        expires_at=credential.expires_at,
    )
    store.provision_budget("alice", "budget", 1000)
    box = SimpleNamespace(
        store=store,
        policy=policy,
        ref=ref,
        alias=alias,
        catalog=catalog,
        target=target,
        credential=credential,
        grant=grant,
        admission=admission,
        fact=fact,
    )
    authority = Authority(
        store,
        target=lambda t, c: box.target,
        grant=lambda t, c: box.grant,
        credential=lambda t, c: box.credential,
        catalog=lambda t, c: box.catalog,
        selector=services.selector,
    )
    keys = ApplicationKeys(store)
    key, raw = keys.issue(
        ctx(),
        expires_at=credential.expires_at,
        scopes=("models:read", "chat:complete", "workflow:run", "runs:read", "runs:cancel"),
        aliases=(alias.id,),
        policies=(ref,),
        max_cost_micro_usd=1000,
    )
    assert asyncio.run(keys.authenticate(raw, datetime.now(UTC))) == key
    inference = RecordedInference()
    gateway = Gateway(authority, inference, keys, streaming_enabled=True)
    runner = WorkflowRunner(gateway, SampleTools({}), retain_seconds=60)
    box.authority, box.keys, box.key, box.raw = authority, keys, key, raw
    box.inference, box.gateway, box.runner = inference, gateway, runner
    box.request = ChatCompletionRequest(
        model=alias.id, messages=({"role": "user", "content": "Synthetic document"},), max_tokens=32
    )
    return box
