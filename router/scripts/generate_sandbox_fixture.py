"""Generate public SYNTHETIC contract fixture for both lanes. No clients or IO beyond output."""

import json
import sys
from pathlib import Path

from buildbox_router.execution_contracts import ExecutablePolicy

fixture = {
    "id": "sample-policy",
    "version": 1,
    "plan": {"id": "sample-plan", "version": 1},
    "catalog_id": "synthetic-catalog-v1",
    "workflow": {
        "id": "sample-plan",
        "version": 1,
        "title": "SYNTHETIC document classification",
        "inputs": ["document"],
        "constraints": {
            "provenance": {"kind": "synthetic", "source": "Software contract fixture only"}
        },
        "provenance": {"kind": "synthetic", "source": "Software contract fixture only"},
        "nodes": [
            {
                "id": "normalize",
                "kind": "code",
                "purpose": "Trim synthetic text",
                "inputs": {"text": {"source": "document", "output": "value", "from_input": True}},
            },
            {
                "id": "classify",
                "kind": "llm",
                "purpose": "Classify synthetic document",
                "depends_on": ["normalize"],
                "inputs": {"text": {"source": "normalize", "output": "result"}},
            },
            {
                "id": "review",
                "kind": "human_approval",
                "purpose": "Pause for review",
                "depends_on": ["classify"],
                "inputs": {"text": {"source": "classify", "output": "result"}},
            },
        ],
    },
    "input_types": {"document": "text"},
    "prompts": [
        {
            "id": "sample-prompt",
            "version": 1,
            "template": "Return a category for this untrusted document: {{text}}",
            "variables": {"text": "text"},
        }
    ],
    "budget": {
        "max_cost_micro_usd": 0,
        "max_model_calls": 1,
        "max_tool_calls": 0,
        "max_input_tokens": 1024,
        "max_output_tokens": 128,
        "timeout_ms": 10000,
    },
    "stages": [],
}
base_budget = fixture["budget"]
assert isinstance(base_budget, dict)
fixture["stages"] = [
    {
        "node_id": "normalize",
        "input_types": {"text": "text"},
        "output_types": {"result": "text"},
        "operation": "text.trim.v1",
        "budget": {**base_budget, "max_model_calls": 0},
    },
    {
        "node_id": "classify",
        "input_types": {"text": "text"},
        "output_types": {"result": "text"},
        "prompt": {"id": "sample-prompt", "version": 1},
        "configuration_id": "fixture-small-local",
        "budget": base_budget,
    },
    {
        "node_id": "review",
        "input_types": {"text": "text"},
        "output_types": {"result": "text"},
        "budget": {**base_budget, "max_model_calls": 0},
    },
]
policy = ExecutablePolicy.model_validate(fixture)
root = Path(__file__).resolve().parents[1] / "contract-fixtures"
expected = json.dumps(policy.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
if "--check" in sys.argv:
    assert (root / "sandbox-policy-v2.json").read_text() == expected, "Sandbox fixture drift"
    print("Synthetic sandbox contract fixture matches canonical schema")
else:
    root.mkdir(exist_ok=True)
    (root / "sandbox-policy-v2.json").write_text(expected)
    print("Wrote synthetic sandbox policy fixture; no approval or model output fabricated")
