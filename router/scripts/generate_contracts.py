"""Deterministic generated artifacts, no startup, storage or network operations."""

import json
from pathlib import Path

from buildbox_router.openapi_schema import canonical_openapi

root = Path(__file__).resolve().parents[1]
schema = canonical_openapi()
(root / "openapi.json").write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
