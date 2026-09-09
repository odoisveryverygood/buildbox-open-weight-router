import json
import subprocess
from pathlib import Path

from buildbox_router.execution_contracts import ExecutablePolicy, ImportedSample

ROOT = Path(__file__).resolve().parents[2]


def test_studio_unit_checks_and_canonical_import_payload():
    result = subprocess.run(
        ["node", "web/tests/unit.cjs", "--payload"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "14 studio unit checks passed" in result.stdout
    payload = next(
        line.removeprefix("PAYLOAD:")
        for line in result.stdout.splitlines()
        if line.startswith("PAYLOAD:")
    )
    sample = ImportedSample.model_validate(json.loads(payload))
    assert sample.data_class == "synthetic" and sample.expected_output is None
    draft_payload = next(
        line.removeprefix("DRAFT:")
        for line in result.stdout.splitlines()
        if line.startswith("DRAFT:")
    )
    policy = ExecutablePolicy.model_validate_json(draft_payload)
    assert policy.quality == "untested_provisional" and policy.production_approved is False
    assert policy.stages[1].configuration_id == "fixture-small-local"


def test_no_parallel_provider_or_secret_storage_path():
    source = "\n".join(p.read_text() for p in (ROOT / "web/src/studio").glob("*.ts*"))
    assert "localStorage" not in source
    assert "sessionStorage" not in source
    assert "dangerouslySetInnerHTML" not in source
    assert "fetch('https://" not in source
    assert 'fetch("https://' not in source
    assert "api.openai.com" not in source
    assert "openrouter.ai/api/v1/chat" not in source
