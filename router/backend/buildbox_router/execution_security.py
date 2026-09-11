"""Shared deterministic sandbox guards. No IO, credentials or model decisions."""

import json
from datetime import datetime

from pydantic import JsonValue

from .contracts import ErrorCode
from .errors import DomainError
from .execution_contracts import (
    ApplicationKeyMetadata,
    ExecutablePolicy,
    PolicyTransition,
    RouteAlias,
    SandboxAdmission,
    Scope,
    ValueType,
    digest,
)


def deny(message: str) -> None:
    raise DomainError(ErrorCode.UNSUPPORTED, message, 403)


def validate_inputs(types: dict[str, ValueType], values: dict[str, JsonValue]) -> None:
    try:
        bounded = len(json.dumps(values, allow_nan=False).encode()) <= 65536
    except (TypeError, ValueError):
        bounded = False
    if not bounded:
        deny("Typed inputs must be finite bounded JSON")
    if set(types) != set(values):
        deny("Missing or unexpected typed inputs")
    for field, kind in types.items():
        value = values[field]
        valid = {
            "text": isinstance(value, str),
            "boolean": type(value) is bool,
            "number": type(value) in (int, float),
            "json": True,
        }[kind]
        if not valid:
            deny("Input value does not satisfy its stage binding type")


def validate_alias(policy: ExecutablePolicy, alias: RouteAlias) -> None:
    if (policy.id, policy.version) != (alias.policy.id, alias.policy.version):
        deny("Alias policy pin mismatch")
    stage = next((s for s in policy.stages if s.node_id == alias.node_id), None)
    if (
        stage is None
        or stage.configuration_id is None
        or stage.configuration_id != alias.configuration_id
    ):
        deny("Chat alias must pin exactly one LLM node and its configuration")


def validate_admission(
    tenant: str,
    policy: ExecutablePolicy,
    admission: SandboxAdmission,
    now: datetime,
    *,
    allow_synthetic: bool = False,
) -> None:
    if admission.tenant_id != tenant or admission.expires_at <= now:
        deny("Missing current tenant-scoped sandbox admission")
    if (admission.policy.id, admission.policy.version) != (
        policy.id,
        policy.version,
    ) or admission.policy_digest != digest(policy):
        deny("Admission does not cover this immutable executable policy")
    configs = {
        c
        for s in policy.stages
        for c in ((s.configuration_id,) if s.configuration_id else ())
        + s.fallback_configuration_ids
    }
    tools = {t for s in policy.stages for t in s.allowed_tool_ids}
    if configs != set(admission.configuration_ids) or tools != set(admission.allowed_tool_ids):
        deny("Admission configuration or tool coverage mismatch")
    for fact in (
        admission.privacy,
        admission.license_policy,
        admission.weights_access,
        admission.capabilities,
        admission.spending,
    ):
        if fact.value is not True or not fact.provenance.evidence_ids:
            deny("Mandatory sandbox fact is unverified or denied")
        if not allow_synthetic and fact.provenance.kind not in ("observed", "documented"):
            deny("Synthetic/inferred/unverified facts are not operational sandbox admission")
    # Quality is intentionally NOT an admission criterion: first tests must be possible.


def authorize_sandbox(
    tenant: str,
    policy: ExecutablePolicy,
    transition: PolicyTransition,
    admission: SandboxAdmission,
    now: datetime,
    *,
    allow_synthetic: bool = False,
) -> None:
    if (
        transition.status != "sandbox_enabled"
        or transition.admission_id != admission.id
        or transition.policy != admission.policy
    ):
        deny("Exact policy version is not sandbox-enabled")
    validate_admission(tenant, policy, admission, now, allow_synthetic=allow_synthetic)


def authorize_application_key(
    tenant: str,
    key: ApplicationKeyMetadata,
    scope: Scope,
    now: datetime,
    *,
    alias: str | None = None,
    policy: ExecutablePolicy | None = None,
) -> None:
    if (
        key.tenant_id != tenant
        or key.revoked_at is not None
        or key.expires_at <= now
        or key.created_at > now
        or scope not in key.scopes
    ):
        deny("Application key scope, tenant, revocation or lifetime denied")
    if alias is not None and alias not in key.alias_ids:
        deny("Application key cannot access this alias")
    if policy is not None and not any(
        (p.id, p.version) == (policy.id, policy.version) for p in key.workflow_policies
    ):
        deny("Application key cannot run this workflow policy")
