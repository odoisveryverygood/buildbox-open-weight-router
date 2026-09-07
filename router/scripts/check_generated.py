"""Verify generated frontend/API contracts without modifying checked-in artifacts."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from buildbox_router.openapi_schema import canonical_openapi

root = Path(__file__).resolve().parents[1]
schema = canonical_openapi()
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
subprocess.run(
    [sys.executable, str(root / "scripts/generate_sandbox_fixture.py"), "--check"], check=True
)
