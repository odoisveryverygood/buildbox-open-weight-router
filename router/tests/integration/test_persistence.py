import os
import subprocess
import sys
import time

import pytest
from buildbox_router.composition import fixture_services
from buildbox_router.contracts import Job, Workflow
from buildbox_router.errors import DomainError
from buildbox_router.worker import run_once
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError


def new_job(workflow):
    now = time.time()
    return Job(
        id="job-test",
        workflow_id=workflow.id,
        workflow_version=1,
        status="queued",
        created_at=now,
        updated_at=now,
    )


def test_ownership_and_immutable_versions(storage, workflow):
    storage.put("owner-a", "workflow", workflow.id, workflow.model_dump_json())
    with pytest.raises(DomainError) as exc:
        storage.get("owner-b", "workflow", workflow.id)
    assert exc.value.status == 404
    with pytest.raises(DomainError):
        storage.put("owner-b", "workflow", workflow.id, workflow.model_dump_json(), 2)
    with pytest.raises(DomainError):
        storage.put("owner-a", "workflow", workflow.id, workflow.model_dump_json())
    second = workflow.model_copy(update={"version": 2})
    storage.put("owner-a", "workflow", workflow.id, second.model_dump_json(), 2)
    assert (
        Workflow.model_validate_json(storage.get("owner-a", "workflow", workflow.id)).version == 1
    )
    with pytest.raises(DatabaseError), storage.engine.begin() as conn:
        conn.execute(text("UPDATE records SET payload='{}'"))


def test_worker_persists_and_new_process_reloads(storage, workflow):
    storage.put("owner", "workflow", workflow.id, workflow.model_dump_json())
    job = new_job(workflow)
    storage.enqueue("owner", job)
    assert run_once(fixture_services(storage))
    assert storage.job("owner", job.id).status == "succeeded"
    env = os.environ.copy()
    env["ROUTER_DATABASE_URL"] = str(storage.engine.url)
    code = "from buildbox_router.config import Settings; from buildbox_router.storage import SqlStorage,engine_for; from buildbox_router.contracts import Recommendation; s=SqlStorage(engine_for(Settings.from_env())); r=Recommendation.model_validate_json(s.get('owner','recommendation','job-test')); assert r.assignments[0].node_id == 'classify'; assert s.job('owner','job-test').status == 'succeeded'; print('new-process reload PASS')"
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    assert "new-process reload PASS" in result.stdout
    assert not run_once(fixture_services(storage))
    with pytest.raises(DomainError):
        storage.job("other-owner", job.id)


def test_job_claim_is_exclusive_and_stale_attempt_cannot_finish(storage, workflow):
    storage.put("owner", "workflow", workflow.id, workflow.model_dump_json())
    storage.enqueue("owner", new_job(workflow))
    owner, first = storage.claim()
    assert storage.claim() is None
    with storage.engine.begin() as conn:
        conn.execute(text("UPDATE jobs SET updated_at=0"))
    _, second = storage.claim()
    assert second.attempts == first.attempts + 1
    services = fixture_services(storage)
    catalog = services.catalog.snapshot()
    rec = services.selector.recommend(workflow, catalog, first.id)
    with pytest.raises(DomainError):
        storage.finish(owner, first, rec, catalog)
    storage.finish(owner, second, rec, catalog)


def test_job_failure_is_persisted_without_exception_secrets(storage, workflow):
    storage.enqueue("owner", new_job(workflow))  # missing workflow -> failed job
    assert run_once(fixture_services(storage))
    assert storage.job("owner", "job-test").status == "failed"
    assert "sqlite" not in storage.job("owner", "job-test").error.message


def test_stale_job_retries_are_bounded(storage, workflow):
    job = new_job(workflow).model_copy(update={"status": "running", "attempts": 3, "updated_at": 0})
    storage.enqueue("owner", job)
    assert storage.claim() is None
    assert storage.job("owner", job.id).status == "failed"
