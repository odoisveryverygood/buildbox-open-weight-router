"""Verify generated frontend/API contracts without modifying checked-in artifacts."""

import json
import subprocess
import tempfile
from pathlib import Path

from buildbox_router.api import create_app
from buildbox_router.contracts import ExecutionTool, ResearchTool
from pydantic import TypeAdapter

root = Path(__file__).resolve().parents[1]
schema = create_app().openapi()
for model in (ResearchTool, ExecutionTool):
    schema["components"]["schemas"][model.__name__] = TypeAdapter(model).json_schema()
expected = json.dumps(schema, indent=2, sort_keys=True) + "\n"
assert (root / "openapi.json").read_text() == expected, "OpenAPI drift: run npm run generate"
with tempfile.TemporaryDirectory(prefix="buildbox-contracts-") as directory:
    output = Path(directory) / "api.ts"
    subprocess.run(
        [
            str(root / "node_modules/.bin/openapi-typescript"),
            str(root / "openapi.json"),
            "-o",
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    assert output.read_text() == (root / "web/src/generated/api.ts").read_text(), (
        "Frontend type drift: run npm run generate"
    )
print("Generated OpenAPI and frontend types match canonical contracts")
