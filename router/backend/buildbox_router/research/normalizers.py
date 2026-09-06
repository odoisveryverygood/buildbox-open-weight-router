"""Deterministic parsers for verified publisher/endpoint metadata structures.

No source prose is a tool instruction. Unknown fields are never executable and
advertised support is never upgraded to behavior measured by our tests.
"""

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from ..contracts import Fact, ModelArtifact, Provenance
from .evidence import claim
from .records import (
    ArtifactRecord,
    ClaimRecord,
    EndpointRecord,
    FreshnessPolicy,
    PriceComponent,
    SourceCapture,
    Status,
    failure,
    object_dict,
    stable_id,
)

REPOSITORY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}/[A-Za-z0-9][A-Za-z0-9_.-]{0,159}")
REVISION = re.compile(r"[0-9a-f]{40}")


def known_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip() and value.lower() not in ("unknown", "n/a"):
        return value
    return None


def string_fact(value: Any, p: Provenance, reason: str) -> Fact[str]:
    value = known_string(value)
    return Fact[str](value=value, provenance=p, unknown_reason=reason if value is None else None)


def int_fact(value: Any, p: Provenance, reason: str) -> Fact[int]:
    valid = isinstance(value, int) and not isinstance(value, bool) and value >= 0
    return Fact[int](
        value=value if valid else None, provenance=p, unknown_reason=None if valid else reason
    )


def parse_json(source: SourceCapture) -> dict[str, Any]:
    def invalid_constant(value: str) -> Any:
        raise ValueError("Nonfinite number")

    try:
        return object_dict(json.loads(source.body, parse_constant=invalid_constant))
    except (ValueError, TypeError, RecursionError):
        raise failure(Status.INVALID, "Invalid structured public metadata", source.id) from None


def artifact_from_hub(
    repository: str, source: SourceCapture, policy: FreshnessPolicy
) -> tuple[ArtifactRecord, tuple[ClaimRecord, ...]]:
    if not REPOSITORY.fullmatch(repository):
        raise failure(Status.INVALID, "Invalid exact publisher/repository identity")
    if source.source_type != "publisher_metadata" or source.url != (
        f"https://huggingface.co/api/models/{repository}"
    ):
        raise failure(Status.INVALID, "Artifact needs its exact publisher metadata source")
    data = parse_json(source)
    if data.get("id") != repository or data.get("author") != repository.split("/")[0]:
        raise failure(Status.CONFLICT, "Publisher/repository identity mismatch", repository)
    revision = data.get("sha")
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise failure(Status.PARTIAL, "Exact immutable repository revision is missing", repository)
    if data.get("private") is not False:
        raise failure(Status.UNSAFE, "Public repository status must be explicit", repository)
    artifact_id = stable_id("artifact", repository, revision)
    card = object_dict(data.get("cardData", {}))
    siblings = data.get("siblings", [])
    if not isinstance(siblings, list):
        raise failure(Status.INVALID, "Invalid repository file listing", repository)
    weights = tuple(
        sorted(
            item["rfilename"]
            for item in siblings
            if isinstance(item, dict)
            and isinstance(item.get("rfilename"), str)
            and re.fullmatch(
                r"(?:[\w.-]+/)*(?:model[\w.-]*\.safetensors|pytorch_model[\w.-]*\.bin|consolidated[\w.-]*\.(?:pth|safetensors))",
                item["rfilename"],
            )
        )
    )
    gated = data.get("gated")
    if gated is False:
        access: str | None = "public weight listing; download not exercised"
    elif gated in ("auto", "manual"):
        access = f"gated ({gated}); individual access and license acceptance not exercised"
    else:
        access = None
    open_weight = True if weights and access and data.get("disabled") is False else None
    declared_license = known_string(card.get("license"))
    if declared_license and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,99}", declared_license):
        declared_license = None
    rows = tuple(
        claim(
            source,
            subject=artifact_id,
            kind="artifact",
            field=field,
            locator=locator,
            text=text,
            policy=policy,
        )
        for field, locator, text in (
            (
                "identity",
                "/id,/author,/sha",
                f"Publisher repository {repository} reports revision {revision}.",
            ),
            (
                "license",
                "/cardData/license",
                f"Publisher license metadata: {declared_license or 'Unknown'}. Terms require source review; this is not legal clearance.",
            ),
            (
                "access",
                "/private,/gated,/disabled,/siblings",
                f"Weight files listed: {len(weights)}. Access: {access or 'Unknown'}. No weights downloaded.",
            ),
        )
    )
    p = Provenance(
        kind="synthetic" if source.synthetic else "documented",
        source=source.url,
        evidence_ids=tuple(row.evidence.id for row in rows),
    )
    license_path = next(
        (
            item.get("rfilename")
            for item in siblings
            if isinstance(item, dict)
            and item.get("rfilename") in ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENSE.GEMMA")
        ),
        None,
    )
    # A discovered file path is a source reference, never evidence that its terms were accepted.
    license_url = (
        f"https://huggingface.co/{repository}/blob/{revision}/{license_path}"
        if license_path
        else known_string(card.get("license_link"))
    )
    if license_url is None and declared_license:
        # A metadata declaration is a valid citation even when no separate license
        # file exists. This does not claim that license terms were read or accepted.
        license_url = source.url
    return (
        ArtifactRecord(
            artifact=ModelArtifact(
                id=artifact_id,
                name=repository,
                revision=revision,
                open_weight=Fact[bool](
                    value=open_weight,
                    provenance=p,
                    unknown_reason="Weight/access declaration incomplete"
                    if open_weight is None
                    else None,
                ),
                license=string_fact(declared_license, p, "Publisher license metadata absent"),
                provenance=p,
            ),
            repository_id=repository,
            repository_url=f"https://huggingface.co/{repository}/tree/{revision}",
            publisher=Fact[str](value=data["author"], provenance=p),
            weight_files=weights,
            access=string_fact(access, p, "Publisher did not declare access conditions"),
            license_url=string_fact(license_url, p, "No publisher license source located"),
            declared_task=string_fact(data.get("pipeline_tag"), p, "Task/modality metadata absent"),
            input_modalities=Fact[tuple[str, ...]](
                provenance=p,
                unknown_reason="A pipeline tag is not an exhaustive input-modality declaration",
            ),
            output_modalities=Fact[tuple[str, ...]](
                provenance=p,
                unknown_reason="Output modalities not separately established in structured publisher metadata",
            ),
            release_date=string_fact(
                None, p, "Repository creation/modification is not model release date"
            ),
            identity_claim_id=rows[0].evidence.id,
        ),
        rows,
    )


TOKEN_COMPONENTS = {
    "prompt",
    "completion",
    "internal_reasoning",
    "input_cache_read",
    "input_cache_write",
}
UNIT_COMPONENTS = {"request": "request", "image": "image", "web_search": "search"}


def prices_from_metadata(raw: Any) -> tuple[PriceComponent, ...]:
    if raw is None:
        return ()
    data = object_dict(raw)
    prices = []
    for component, value in sorted(data.items()):
        if component == "overrides":
            continue
        # Unknown units remain unknown; e.g. discount is not USD/token.
        unit = (
            "token" if component in TOKEN_COMPONENTS else UNIT_COMPONENTS.get(component, "unknown")
        )
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise failure(Status.INVALID, "Price component has an invalid representation")
        try:
            amount = Decimal(str(value))
            if not amount.is_finite() or amount < 0:
                raise ValueError("Invalid amount")
            prices.append(
                PriceComponent.model_validate(
                    {
                        "component": component,
                        "raw_amount": str(value),
                        "unit": unit,
                        "currency": "unknown" if unit == "unknown" else "USD",
                        "usd_per_million_tokens": str(amount * 1_000_000)
                        if unit == "token"
                        else None,
                    }
                )
            )
        except (InvalidOperation, ValueError):
            raise failure(Status.INVALID, "Nonfinite, negative or invalid price") from None
    return tuple(prices)


def endpoints_from_openrouter(
    artifact: ArtifactRecord,
    model_source: SourceCapture,
    endpoint_source: SourceCapture,
    policy: FreshnessPolicy,
) -> tuple[tuple[EndpointRecord, ...], tuple[ClaimRecord, ...]]:
    if (
        model_source.source_type != "official_endpoint"
        or endpoint_source.source_type != "official_endpoint"
    ):
        raise failure(Status.INVALID, "Endpoint facts require official endpoint sources")
    model = object_dict(parse_json(model_source).get("data"))
    data = object_dict(parse_json(endpoint_source).get("data"))
    slug = model.get("id")
    if not isinstance(slug, str) or not REPOSITORY.fullmatch(slug):
        raise failure(Status.INVALID, "Exact routing model ID missing")
    if (
        model_source.url != f"https://openrouter.ai/api/v1/model/{slug}"
        or endpoint_source.url != f"https://openrouter.ai/api/v1/models/{slug}/endpoints"
    ):
        raise failure(Status.CONFLICT, "Routing model/source identity mismatch")
    if data.get("id") != slug or model.get("hugging_face_id") != artifact.repository_id:
        raise failure(Status.CONFLICT, "Explicit publisher-to-endpoint identity mapping missing")
    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list):
        raise failure(Status.INVALID, "Endpoint list missing")
    records: list[EndpointRecord] = []
    claims: list[ClaimRecord] = []
    for item in endpoints:
        ep = object_dict(item)
        tag = known_string(ep.get("tag"))
        name = known_string(ep.get("name"))
        provider = known_string(ep.get("provider_name"))
        if tag is None or name is None or provider is None or ep.get("model_id") != slug:
            raise failure(Status.CONFLICT, "Endpoint identity incomplete or mismatched")
        endpoint_id = stable_id("endpoint", slug, tag, name, str(ep.get("quantization")))
        rows = (
            claim(
                model_source,
                subject=endpoint_id,
                kind="endpoint",
                field="identity",
                locator="/data/id,/data/hugging_face_id",
                text=f"Routing identity {slug} maps to publisher repository {artifact.repository_id}; served revision is undisclosed.",
                policy=policy,
                limitations=("Repository mapping does not pin hosted weight revision.",),
            ),
            claim(
                endpoint_source,
                subject=endpoint_id,
                kind="endpoint",
                field="deployment",
                locator=f"/data/endpoints/{len(records)}",
                text=f"Provider {provider}; endpoint {name}; parameters and limits are provider declarations, not our measurements.",
                policy=policy,
                limitations=(
                    "No endpoint invocation; served revision, hardware and privacy may be opaque.",
                ),
            ),
            claim(
                endpoint_source,
                subject=endpoint_id,
                kind="endpoint",
                field="pricing",
                locator=f"/data/endpoints/{len(records)}/pricing",
                text="Provider-specific advertised component prices; no workload blend or measured invoice.",
                policy=policy,
                limitations=(
                    "Prices may change; unknown units and conditional overrides are preserved.",
                ),
            ),
        )
        claims.extend(rows)
        p = Provenance(
            kind="synthetic" if endpoint_source.synthetic else "documented",
            source=endpoint_source.url,
            evidence_ids=tuple(row.evidence.id for row in rows),
        )
        raw_params = ep.get("supported_parameters")
        valid_params = isinstance(raw_params, list) and all(isinstance(x, str) for x in raw_params)
        raw_prices = object_dict(ep.get("pricing", {}))
        restrictions = ep.get("supports_tool_choice")
        records.append(
            EndpointRecord(
                id=endpoint_id,
                artifact_id=artifact.artifact.id,
                routing_model_id=slug,
                endpoint_tag=tag,
                provider=Fact[str](value=provider, provenance=p),
                metadata_url=endpoint_source.url,
                serving_url=string_fact(None, p, "Exact upstream serving URL undisclosed"),
                served_revision=string_fact(None, p, "Hosted repository revision not declared"),
                supported_parameters=Fact[tuple[str, ...]](
                    value=tuple(raw_params)
                    if valid_params and isinstance(raw_params, list)
                    else None,
                    provenance=p,
                    unknown_reason=None
                    if valid_params
                    else "Endpoint parameter list missing or invalid",
                ),
                context_tokens=int_fact(ep.get("context_length"), p, "Context ceiling unknown"),
                max_prompt_tokens=int_fact(
                    ep.get("max_prompt_tokens"), p, "Prompt ceiling unknown"
                ),
                max_completion_tokens=int_fact(
                    ep.get("max_completion_tokens"), p, "Completion ceiling unknown"
                ),
                quantization=string_fact(
                    ep.get("quantization"), p, "Provider quantization unknown"
                ),
                hardware=string_fact(None, p, "Provider hardware undisclosed"),
                region=string_fact(None, p, "Endpoint residency not established"),
                privacy=string_fact(None, p, "Endpoint retention/training policy not established"),
                provider_restrictions=string_fact(
                    json.dumps(restrictions, sort_keys=True) if restrictions is not None else None,
                    p,
                    "Per-mode tool-choice restrictions unknown",
                ),
                prices=prices_from_metadata(raw_prices),
                conditional_pricing=string_fact(
                    json.dumps(raw_prices["overrides"], sort_keys=True)
                    if "overrides" in raw_prices
                    else None,
                    p,
                    "Conditional pricing not supplied; absence is not proof of no overrides",
                ),
                evidence_ids=p.evidence_ids,
                limitations=(
                    "Advertised capabilities only; no endpoint tests.",
                    "Exact hosted reproducibility is unknown.",
                ),
            )
        )
    return tuple(records), tuple(claims)
