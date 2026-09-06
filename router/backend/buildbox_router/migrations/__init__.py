"""Integration-owned, forward-only schema migrations, run explicitly before serving."""

from sqlalchemy import Connection, Engine, text

REVISION = 2


def migrate(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE IF NOT EXISTS schema_revisions (version INTEGER PRIMARY KEY)")
        )
        current = conn.execute(text("SELECT MAX(version) FROM schema_revisions")).scalar() or 0
        if current > REVISION:
            raise RuntimeError("Database schema is newer than this application")
        if current < 1:
            revision_one(conn, engine.dialect.name)
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES (1)"))
        if current < 2:
            revision_two(conn)
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES (2)"))


def revision_two(conn: Connection) -> None:
    conn.execute(
        text(
            "CREATE TABLE approval_budgets (id VARCHAR(80) PRIMARY KEY, cap_micro INTEGER NOT NULL, held_micro INTEGER NOT NULL)"
        )
    )
    conn.execute(
        text("""CREATE TABLE jobs_v2 (
        id VARCHAR(80) PRIMARY KEY, owner VARCHAR(80) NOT NULL,
        status VARCHAR(20) NOT NULL CHECK(status IN ('queued','running','succeeded','failed','cancelled','uncertain')),
        updated_at DOUBLE PRECISION NOT NULL, attempts INTEGER NOT NULL, payload TEXT NOT NULL)""")
    )
    conn.execute(text("INSERT INTO jobs_v2 SELECT * FROM jobs"))
    conn.execute(text("DROP TABLE jobs"))
    conn.execute(text("ALTER TABLE jobs_v2 RENAME TO jobs"))
    conn.execute(text("CREATE INDEX jobs_queue ON jobs(status, updated_at)"))
    conn.execute(
        text("""CREATE TABLE submissions (
        owner VARCHAR(80) NOT NULL, request_key VARCHAR(80) NOT NULL, input_hash VARCHAR(64) NOT NULL,
        plan_id VARCHAR(80) NOT NULL, version INTEGER NOT NULL, job_id VARCHAR(80) NOT NULL,
        PRIMARY KEY(owner, request_key))""")
    )
    conn.execute(
        text("""CREATE TABLE provider_calls (
        id VARCHAR(80) PRIMARY KEY, owner VARCHAR(80) NOT NULL, job_id VARCHAR(80) NOT NULL,
        role VARCHAR(80) NOT NULL, approval_id VARCHAR(80) NOT NULL,
        state VARCHAR(20) NOT NULL, reserved_micro INTEGER NOT NULL,
        actual_micro INTEGER, metadata TEXT NOT NULL)""")
    )


def revision_one(conn: Connection, dialect: str) -> None:
    conn.execute(
        text("""CREATE TABLE records (
        kind VARCHAR(40) NOT NULL, id VARCHAR(80) NOT NULL,
        version INTEGER NOT NULL CHECK(version > 0), owner VARCHAR(80) NOT NULL,
        payload TEXT NOT NULL, PRIMARY KEY(kind, id, version))""")
    )
    conn.execute(text("CREATE INDEX records_owner ON records(owner, kind)"))
    conn.execute(
        text("""CREATE TABLE jobs (
        id VARCHAR(80) PRIMARY KEY, owner VARCHAR(80) NOT NULL,
        status VARCHAR(20) NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
        updated_at DOUBLE PRECISION NOT NULL, attempts INTEGER NOT NULL,
        payload TEXT NOT NULL)""")
    )
    conn.execute(text("CREATE INDEX jobs_queue ON jobs(status, updated_at)"))
    if dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            conn.execute(
                text(
                    f"CREATE TRIGGER immutable_records_{action.lower()} BEFORE {action} ON records BEGIN SELECT RAISE(ABORT, 'Records are immutable; append a version'); END"
                )
            )
    elif dialect == "postgresql":
        conn.execute(
            text("""CREATE FUNCTION reject_record_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
          BEGIN RAISE EXCEPTION 'Records are immutable; append a version'; END; $$""")
        )
        conn.execute(
            text(
                "CREATE TRIGGER immutable_records BEFORE UPDATE OR DELETE ON records FOR EACH ROW EXECUTE FUNCTION reject_record_mutation()"
            )
        )
    else:
        raise RuntimeError("Unsupported migration dialect")
