"""Deterministic disclosed checks, not model self-grading or general quality claims."""

import json
from typing import Literal

from pydantic import JsonValue

from .execution_contracts import ImportedSample, SampleCheck
from .json_contracts import parse_json


def checks(sample: ImportedSample, output: JsonValue) -> tuple[SampleCheck, ...]:
    # Workflow outputs have an explicit result envelope; expected_output describes its value.
    value = (
        output.get("result") if isinstance(output, dict) and set(output) == {"result"} else output
    )
    result = []
    status: Literal["pass", "fail"]
    if sample.output_schema:
        try:
            parsed = parse_json(value) if isinstance(value, str) else value
            sample.output_schema.validate_value(parsed)
            status = "pass"
        except ValueError:
            status = "fail"
        result.append(
            SampleCheck(
                check="json_schema",
                status=status,
                detail="Deterministic strict schema check; not semantic accuracy",
            )
        )
    if sample.expected_reviewed:
        expected = sample.expected_output
        if isinstance(expected, (dict, list)) and isinstance(value, str):
            try:
                value = parse_json(value)
            except ValueError:
                pass
        matched = json.dumps(value, sort_keys=True, allow_nan=False) == json.dumps(
            expected, sort_keys=True, allow_nan=False
        )
        result.append(
            SampleCheck(
                check="reviewed_exact_match",
                status="pass" if matched else "fail",
                detail=f"Exact match against user-reviewed expected output; split={sample.split}. One sample does not establish quality.",
            )
        )
    else:
        result.append(
            SampleCheck(
                check="reviewed_exact_match",
                status="not_run",
                detail="No reviewed ground truth. Observed historical model answers are never treated as expected answers.",
            )
        )
    return tuple(result)
