"""Fail-closed authority and cost checks, independent of transport implementations."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal

from ..contracts import CatalogSnapshot, ErrorCode, Fact, Provenance
from ..errors import DomainError
from ..execution_contracts import (
    ChatCompletionRequest,
    DecisionTrace,
    ExecutablePolicy,
    ExecutableStage,
    ProviderCredentialReference,
    RuntimeGrant,
    SandboxAdmission,
    TargetConfiguration,
    VersionRef,
)
from ..execution_ports import RequestContext
from ..execution_security import authorize_sandbox
from ..execution_storage import SandboxStorage
from ..ports import Selector


def denied(message: str) -> None:
    raise DomainError(ErrorCode.UNSUPPORTED, message, 403)


def unknown_identity() -> Fact[str]:
    return Fact[str](
        provenance=Provenance(kind="inference", source="No served identity observation"),
        unknown_reason="Provider identity not observed",
    )


@dataclass(frozen=True)
class AuthorizedStage:
    policy: ExecutablePolicy
    stage: ExecutableStage
    admission: SandboxAdmission
    target: TargetConfiguration
    credential: ProviderCredentialReference
    trace: DecisionTrace
    data_class: str


class Authority:
    def __init__(
        self,
        store: SandboxStorage,
        *,
        target: Callable[[str, str], TargetConfiguration],
        grant: Callable[[str, str], RuntimeGrant],
        credential: Callable[[str, str], ProviderCredentialReference],
        catalog: Callable[[str, str], CatalogSnapshot],
        selector: Selector,
    ) -> None:
        self.store, self.target, self.grant = store, target, grant
        self.credential, self.catalog, self.selector = credential, catalog, selector

    def policy(
        self, context: RequestContext, ref: VersionRef
    ) -> tuple[ExecutablePolicy, SandboxAdmission, int]:
        context.check_cancelled()
        if datetime.now(UTC) >= context.deadline:
            denied("Request deadline elapsed")
        view = self.store.policy(context.tenant_id, ref)
        if not view.transition.admission_id:
            denied("Sandbox is not enabled")
        admission = SandboxAdmission.model_validate_json(
            self.store.read(
                context.tenant_id, "admission", view.transition.admission_id or "missing"
            )
        )
        authorize_sandbox(
            context.tenant_id,
            view.policy,
            view.transition,
            admission,
            datetime.now(UTC),
            allow_synthetic=self.store.offline_contract_test,
        )
        return view.policy, admission, view.transition.sequence

    def stage(
        self,
        context: RequestContext,
        ref: VersionRef,
        node_id: str,
        *,
        alias: str | None = None,
        data_class: str = "tenant_private",
    ) -> AuthorizedStage:
        policy, admission, sequence = self.policy(context, ref)
        stage = next((s for s in policy.stages if s.node_id == node_id), None)
        if stage is None or not stage.configuration_id:
            denied("Only pinned LLM stages can use inference")
        assert stage is not None and stage.configuration_id
        target = self.target(context.tenant_id, stage.configuration_id)
        if (
            target.configuration.id != stage.configuration_id
            or target.catalog_id != policy.catalog_id
        ):
            denied("Target does not match immutable catalog pin")
        catalog = self.catalog(context.tenant_id, policy.catalog_id)
        if catalog.synthetic and not self.store.offline_contract_test:
            denied("Synthetic catalog is not an operational target")
        if catalog.id != policy.catalog_id or target.configuration not in catalog.configurations:
            denied("Configuration drift from pinned catalog")
        filtered = self.selector.filter(policy.workflow, catalog)
        if stage.configuration_id not in filtered.eligible:
            denied("Hard eligibility evidence is contradicted or unknown")
        grant = self.grant(context.tenant_id, stage.configuration_id)
        if (
            grant.tenant_id != context.tenant_id
            or grant.expires_at <= datetime.now(UTC)
            or stage.configuration_id not in grant.configuration_ids
            or data_class not in grant.allowed_data_classes
            or grant.budget_reference != admission.budget_reference
        ):
            denied("Target grant does not authorize this data/configuration/budget")
        references = set(grant.credential_reference_ids) & set(admission.credential_reference_ids)
        if len(references) != 1:
            denied("An exact unambiguous credential binding is required")
        credential = self.credential(context.tenant_id, next(iter(references)))
        if (
            credential.id not in references
            or credential.tenant_id != context.tenant_id
            or credential.expires_at <= datetime.now(UTC)
            or credential.adapter_id != ("local_ollama" if target.local else "openrouter")
        ):
            denied("Credential scope or adapter mismatch")
        trace = DecisionTrace(
            request_id=context.request_id,
            tenant_id=context.tenant_id,
            policy=ref,
            transition_sequence=sequence,
            alias_id=alias,
            node_id=node_id,
            configuration_id=stage.configuration_id,
            catalog_id=policy.catalog_id,
            prompt=stage.prompt,
            admission_id=admission.id,
            evidence_ids=tuple(
                sorted(
                    {
                        e
                        for fact in (
                            admission.privacy,
                            admission.license_policy,
                            admission.weights_access,
                            admission.capabilities,
                            admission.spending,
                        )
                        for e in fact.provenance.evidence_ids
                    }
                )
            ),
            requested_endpoint=target.endpoint.endpoint_tag
            if target.endpoint
            else "ollama-loopback-11444",
            served_model=unknown_identity(),
            served_endpoint=unknown_identity(),
            quality=policy.quality,
        )
        return AuthorizedStage(policy, stage, admission, target, credential, trace, data_class)


def input_bound(request: ChatCompletionRequest) -> int:
    # Conservative UTF-8 byte envelope plus bounded message overhead, NOT token measurement.
    return sum(len(m.content.encode("utf-8")) + 32 for m in request.messages) + 128


def cost_bound(target: TargetConfiguration, input_tokens: int, output_tokens: int) -> int:
    if target.local:
        return 0  # No provider charge, NOT zero infrastructure cost.
    endpoint = target.endpoint
    assert endpoint
    prices = {p.component: p for p in endpoint.prices}
    if (
        len(prices) != len(endpoint.prices)
        or not {"prompt", "completion", "request"} <= prices.keys()
        or endpoint.conditional_pricing.value != "none"
    ):
        denied("Complete unconditional price components required for a hard cap")
    total = Decimal(0)
    for name, price in prices.items():
        if price.currency != "USD":
            denied("Unknown price currency")
        if name in ("prompt", "completion") and price.unit == "token":
            total += Decimal(price.raw_amount) * (
                input_tokens if name == "prompt" else output_tokens
            )
        elif name == "request" and price.unit == "request":
            if Decimal(price.raw_amount) != 0:
                denied(
                    "Nonzero request surcharge has no enforced upstream price ceiling in this subset"
                )
        elif Decimal(price.raw_amount) != 0 or price.unit == "unknown":
            denied("Extra billed component lacks a defensible quantity bound")
    return int((total * 1000000).to_integral_value(rounding=ROUND_CEILING))


def preflight(value: AuthorizedStage, request: ChatCompletionRequest) -> int:
    budget, target = value.stage.budget, value.target
    count = input_bound(request)
    if count > budget.max_input_tokens or request.max_tokens > budget.max_output_tokens:
        denied("Incoming token envelope exceeds stage bounds")
    if target.local:
        parameters = target.local.supported_parameters.value
        context, output = target.local.context_tokens.value, target.local.max_output_tokens.value
        if target.local.weights_digest.value is None or target.local.privacy.value != "local_only":
            denied("Local identity/privacy evidence missing")
        if (
            context is None
            or output is None
            or count + request.max_tokens > context
            or request.max_tokens > output
        ):
            denied("Local effective context/output bound unknown or exceeded")
    else:
        assert target.endpoint
        endpoint = target.endpoint
        parameters = endpoint.supported_parameters.value
        limit = endpoint.effective_output_limit(count)
        if limit is None or request.max_tokens > limit:
            denied("Endpoint effective context/output bound unknown or exceeded")
        if endpoint.privacy.value != "zdr" or endpoint.provider_restrictions.value != "none":
            denied("Endpoint privacy/restriction evidence is unsupported or unknown")
        if endpoint.routing_model_id == "openrouter/auto" or ":" in endpoint.routing_model_id:
            denied("Opaque router/model variants are forbidden")
    required = {"max_tokens"} | ({"temperature"} if request.temperature is not None else set())
    if parameters is None or not required <= set(parameters):
        denied("Endpoint cannot satisfy all requested parameters")
    amount = cost_bound(target, count, request.max_tokens)
    if amount > budget.max_cost_micro_usd:
        denied("Maximum possible provider charge exceeds stage cap")
    return amount
