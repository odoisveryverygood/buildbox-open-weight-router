"""Bounded, transparent rules. Never sends a workload to research or inference."""

import re

from ..contracts import WorkloadProfile
from ..routing_contracts import WorkloadRequest


def override(profile: WorkloadProfile, values: WorkloadProfile | None) -> WorkloadProfile:
    if values is None:
        return profile
    fields = values.model_fields_set - {
        "schema_version",
        "evidence",
        "explicit_fields",
        "questions",
        "analyzer_version",
    }
    data = {k: getattr(values, k) for k in fields}
    evidence = profile.evidence | {k: "explicit user override" for k in fields}
    return WorkloadProfile.model_validate(
        profile.model_dump()
        | data
        | {
            "evidence": evidence,
            "explicit_fields": tuple(sorted(set(profile.explicit_fields) | fields)),
        }
    )


def analyze(request: WorkloadRequest) -> WorkloadProfile:
    text = request.description.lower()
    rules = (
        ("debugging", r"debug|fix.*bug|stack trace"),
        ("coding", r"code|implement|function|program"),
        ("structured_extraction", r"extract.*(?:json|schema)|(?:json|schema).*extract"),
        ("extraction", r"extract|parse.*document"),
        ("classification", r"classify|classification|categorize"),
        ("long_context", r"long.context|large document|whole repository"),
        ("summarization", r"summari[sz]|summary"),
        ("mathematics", r"mathemat|equation|theorem"),
        ("science", r"scientific|chemistry|physics"),
        ("vision", r"image|photograph|visual"),
        ("multilingual", r"translat|multilingual"),
        ("research", r"research|sources|citations"),
        ("planning", r"plan|decompos"),
        ("tool_use", r"tool|lookup"),
    )
    task = next((name for name, pattern in rules if re.search(pattern, text)), "general")
    required = ["text_input", "text_output"]
    for token, capability in (
        ("image", "image_input"),
        ("audio", "audio_input"),
        ("video", "video_input"),
    ):
        if token in text:
            required.append(capability)
    structured = "schema_json" if "schema" in text else "json" if "json" in text else "text"
    if structured != "text":
        required.append("schema_json" if structured == "schema_json" else "json_output")
    if re.search(r"tool.call|use.*tools?", text):
        required.append("tools")
    data = {
        "task": task,
        "required": tuple(required),
        "structured_output": structured,
        "local_only": bool(re.search(r"local.only|no external|air.gapped", text)),
        "self_hosted_only": "self-hosted" in text,
        "no_retention": "no retention" in text,
        "complexity": "complex"
        if re.search(r"complex|security|verify|multi.stage", text)
        else "unknown",
        "decomposition": True if "multi-stage" in text else None,
        "parallel": True if "parallel" in text else None,
        "verification": True if re.search(r"verify|validate|correctness", text) else None,
        "evidence": {
            "task": f"keyword rule: {task}",
            "required": "explicit modality/output keywords",
            "privacy": "explicit local/self-hosted/retention phrases",
        },
    }
    profile = override(WorkloadProfile.model_validate(data), request.overrides)
    # Mandatory implied outputs cannot be weakened by an inconsistent capability list.
    caps = set(profile.required)
    if profile.structured_output != "text":
        caps.add("schema_json" if profile.structured_output == "schema_json" else "json_output")
    if profile.tools:
        caps.add("tools")
    questions = []
    if profile.input_tokens is None:
        questions.append("What input token envelope should each stage support?")
    if profile.output_tokens is None:
        questions.append("What is the maximum output token count per stage?")
    if profile.determinism == "required":
        questions.append(
            "Exact deterministic model output is not established by temperature alone."
        )
    return WorkloadProfile.model_validate(
        profile.model_dump() | {"required": tuple(sorted(caps)), "questions": tuple(questions)}
    )
