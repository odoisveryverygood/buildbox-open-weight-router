"""Explicit synthetic revision-2 upgrade check on an EMPTY isolated loopback database."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from buildbox_router.config import Settings
from buildbox_router.errors import DomainError
from buildbox_router.execution_contracts import (
    ExecutablePolicy,
    RouteAlias,
    TransitionRequest,
    VersionRef,
)
from buildbox_router.execution_storage import SandboxStorage
from buildbox_router.migrations import migrate, revision_one, revision_two
from buildbox_router.storage import engine_for
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def main() -> None:
    settings = Settings.from_env()
    if not settings.database_url.startswith("postgresql+psycopg://"):
        raise SystemExit("Requires an isolated loopback PostgreSQL database")
    engine = engine_for(settings)
    with engine.begin() as conn:
        if conn.execute(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        ).scalar_one():
            raise SystemExit("Refusing nonempty database")
        conn.execute(text("CREATE TABLE schema_revisions(version INTEGER PRIMARY KEY)"))
        revision_one(conn, "postgresql")
        revision_two(conn)
        conn.execute(text("INSERT INTO schema_revisions VALUES(1),(2)"))
        conn.execute(text("INSERT INTO records VALUES('test','legacy',1,'alice','preserved')"))
    migrate(engine)
    migrate(engine)
    store = SandboxStorage(engine)
    store.check_revision()
    assert store.get("alice", "test", "legacy") == "preserved"
    policy = ExecutablePolicy.model_validate_json(
        (
            Path(__file__).resolve().parents[1] / "contract-fixtures/sandbox-policy-v2.json"
        ).read_text()
    )
    store._append_policy("alice", policy)
    ref = VersionRef(id=policy.id, version=policy.version)
    store.create_alias(
        "alice",
        RouteAlias(
            id="documents",
            policy=ref,
            node_id="classify",
            configuration_id="fixture-small-local",
            created_at=datetime.now(UTC),
        ),
    )
    try:
        store.alias("bob", "documents")
    except DomainError:
        pass
    else:
        raise AssertionError("Tenant boundary failed")
    store.transition("alice", ref, TransitionRequest(expected_sequence=1, status="disabled"))
    try:
        with engine.begin() as conn:
            conn.execute(text("UPDATE sandbox_records SET payload='{}'"))
    except DBAPIError:
        pass
    else:
        raise AssertionError("Immutable sandbox trigger missing")
    store.provision_budget("alice", "cap", 10)

    def reserve(i: int) -> bool:
        try:
            store.reserve("alice", "cap", f"r{i}", f"q{i}", 10)
            return True
        except DomainError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, range(2))) == 1
    engine.dispose()
    print(
        "PASS PostgreSQL v2->v5, rerun, preserved legacy, immutable aliases/policies, tenant isolation, disabled transition, concurrent sandbox budget"
    )


if __name__ == "__main__":
    main()
