"""Explicit isolated PostgreSQL runtime check; recorded inference, no live model."""

from buildbox_router.api import create_app
from buildbox_router.composition import fixture_services
from buildbox_router.config import Settings
from buildbox_router.execution_comparisons import Comparisons
from buildbox_router.execution_jobs import QueuedWorkflows
from buildbox_router.execution_ports import ExecutionServices
from buildbox_router.execution_storage import SandboxStorage
from buildbox_router.migrations import migrate
from buildbox_router.planning_storage import PlanningStorage
from buildbox_router.storage import engine_for
from buildbox_router.worker import run_once
from fastapi.testclient import TestClient
from sqlalchemy import text

from .conftest import rt


def main():
    settings = Settings.from_env()
    if not settings.database_url.startswith("postgresql+psycopg://"):
        raise SystemExit("Requires empty isolated loopback PostgreSQL database")
    engine = engine_for(settings)
    with engine.connect() as conn:
        if conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        ).scalar_one():
            raise SystemExit("Refusing nonempty database")
    migrate(engine)
    fixture = rt.__wrapped__(PlanningStorage(engine))
    workflows = QueuedWorkflows(fixture.runner)
    execution = ExecutionServices(fixture.gateway, workflows, fixture.keys, Comparisons(workflows))
    services = fixture_services(PlanningStorage(engine))
    app = create_app(settings, services, execution, fixture.store)
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer " + fixture.raw, "Idempotency-Key": "pg-7b-workflow"}
        request = {
            "policy": fixture.ref.model_dump(),
            "inputs": {"document": "   synthetic PG input   "},
        }
        response = client.post("/api/sandbox/runs", headers=headers, json=request)
        assert response.status_code == 202, response.status_code
        saved = response.json()
        assert saved["status"] == "queued"
        assert run_once(services, execution=execution)
        assert not run_once(services, execution=execution)
        result = client.get("/api/sandbox/runs/" + saved["id"], headers=headers).json()
        assert result["status"] == "awaiting_approval"
        assert (
            client.post("/api/sandbox/runs", headers=headers, json=request).json()["id"]
            == saved["id"]
        )
        assert len(fixture.inference.calls) == 1
        fresh = SandboxStorage(engine)
        attempts = fresh.attempts("alice", saved["id"])
        assert len(attempts) == 1 and attempts[0].usage.actual_micro_usd == 0
        assert not fresh.attempts("bob", saved["id"])
        assert fresh.trace("alice", attempts[0].id).policy == fixture.ref
    engine.dispose()
    print(
        "PASS PostgreSQL 7B: HTTP application auth, atomic queue/idempotency, worker, checkpoint, run-scoped attempt query, trace/accounting, ownership; RECORDED inference only"
    )


if __name__ == "__main__":
    main()
