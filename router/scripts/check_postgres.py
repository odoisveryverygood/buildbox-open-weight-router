"""Explicit isolated PostgreSQL check. Never use against an existing/shared database."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from buildbox_router.api import create_app
from buildbox_router.composition import fixture_services
from buildbox_router.config import Settings
from buildbox_router.errors import DomainError
from buildbox_router.migrations import migrate
from buildbox_router.planning import planning_examples
from buildbox_router.planning_contracts import PlanInput
from buildbox_router.planning_storage import PlanningStorage
from buildbox_router.storage import engine_for
from buildbox_router.worker import run_once
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def main():
    settings = Settings.from_env()
    if not settings.database_url.startswith("postgresql+psycopg://"):
        raise SystemExit("Set ROUTER_DATABASE_URL to an isolated loopback PostgreSQL database")
    engine = engine_for(settings)
    with engine.connect() as conn:
        if conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        ).scalar_one():
            raise SystemExit("Refusing nonempty database; use a fresh isolated cluster")
    migrate(engine)
    migrate(engine)
    store = PlanningStorage(engine)
    store.check_revision()
    services = fixture_services(store)
    with TestClient(create_app(services=services)) as client:
        data = PlanInput(intake=planning_examples()[0].intake).model_dump(mode="json")
        response = client.post(
            "/api/plans", json=data, headers={"Idempotency-Key": "postgres-plan-0001"}
        )
        assert response.status_code == 201, response.text
        first = response.json()
        run_once(services)
        path = f"/api/plans/{first['plan']['id']}/versions/1"
        assert client.get(path).json()["result"]["status"] == "provisional"
        assert client.post(path + "/policy", json={}).json()["active"] is False
        revised = client.post(
            path + "/revise", json=data, headers={"Idempotency-Key": "postgres-plan-0002"}
        )
        assert revised.status_code == 201
        run_once(services)
        assert client.get(path).json()["stale"]
        assert client.post(path + "/policy", json={}).status_code == 409
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE records SET payload='{}'"))
    except DBAPIError:
        pass
    else:
        raise AssertionError("Immutable record trigger missing")
    for _ in range(2):
        store.submit("budget-owner", uuid4().hex, PlanInput(intake=planning_examples()[0].intake))
    claims = [store.claim(), store.claim()]

    def reserve(claim):
        owner, job = claim
        try:
            return store.reserve_call(owner, job, "interpretation", "pg-shared-cap", 1000, 1000)
        except DomainError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(x is not None for x in pool.map(reserve, claims)) == 1
    engine.dispose()
    print(
        "PASS PostgreSQL: clean migration, rerun, API/worker/policy, versions/staleness, immutability, concurrent approval cap"
    )


if __name__ == "__main__":
    main()
