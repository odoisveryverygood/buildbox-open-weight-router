import json
from datetime import timedelta
from pathlib import Path

import pytest
from buildbox_router.research.jobs import ResearchPlan
from buildbox_router.research.records import FreshnessPolicy, SourceCapture
from buildbox_router.research.sources import RecordedSources

PUBLIC = Path(__file__).parent / "public"


@pytest.fixture
def captures():
    return tuple(
        SourceCapture.model_validate(x)
        for x in json.loads((PUBLIC / "sources-2026-09-06.json").read_text())
    )


@pytest.fixture
def sources(captures):
    return RecordedSources(captures)


@pytest.fixture
def plan():
    return ResearchPlan.model_validate_json((PUBLIC / "plan-2026-09-06.json").read_text())


@pytest.fixture
def now(captures):
    return max(c.observed_at for c in captures) + timedelta(seconds=1)


@pytest.fixture
def freshness():
    return FreshnessPolicy()


@pytest.fixture
def hub(captures):
    return next(c for c in captures if c.url == "https://huggingface.co/api/models/Qwen/Qwen3-8B")


@pytest.fixture
def model_source(captures):
    return next(c for c in captures if c.id == "openrouter-qwen-mapping")


@pytest.fixture
def endpoint_source(captures):
    return next(c for c in captures if c.id == "openrouter-endpoints-1")
