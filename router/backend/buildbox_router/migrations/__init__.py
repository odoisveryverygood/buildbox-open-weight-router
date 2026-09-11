"""Integration-owned, forward-only schema migrations, run explicitly before serving."""

from sqlalchemy import Connection, Engine, text

REVISION = 4


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
        if current < 3:
            revision_three(conn, engine.dialect.name)
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES (3)"))
        if current < 4:
            revision_four(conn)
            conn.execute(text("INSERT INTO schema_revisions(version) VALUES (4)"))


def revision_four(conn: Connection) -> None:
    conn.execute(
        text("""CREATE TABLE runtime_queue (
        owner VARCHAR(80) NOT NULL, id VARCHAR(80) NOT NULL, request_key VARCHAR(80) NOT NULL,
        principal_id VARCHAR(80) NOT NULL, key_id VARCHAR(80), deadline DOUBLE PRECISION NOT NULL,
        state VARCHAR(20) NOT NULL CHECK(state IN ('queued','running','done','uncertain')),
        lease_until DOUBLE PRECISION,
        PRIMARY KEY(owner,id))""")
    )
    conn.execute(text("CREATE INDEX runtime_queue_ready ON runtime_queue(state,deadline)"))


def revision_three(conn: Connection, dialect: str) -> None:
    # v1 records are untouched. v2 natural IDs (aliases/prompts) are tenant-local.
    conn.execute(
        text("""CREATE TABLE sandbox_records (
        owner VARCHAR(80) NOT NULL, kind VARCHAR(40) NOT NULL, id VARCHAR(80) NOT NULL,
        version INTEGER NOT NULL CHECK(version > 0), payload TEXT NOT NULL,
        PRIMARY KEY(owner, kind, id, version))""")
    )
    conn.execute(
        text("""CREATE TABLE sandbox_heads (
        owner VARCHAR(80) NOT NULL, policy_id VARCHAR(80) NOT NULL,
        policy_version INTEGER NOT NULL, sequence INTEGER NOT NULL CHECK(sequence > 0),
        PRIMARY KEY(owner, policy_id, policy_version))""")
    )
    conn.execute(
        text("""CREATE TABLE sandbox_budgets (
        owner VARCHAR(80) NOT NULL, id VARCHAR(80) NOT NULL,
        cap_micro BIGINT NOT NULL CHECK(cap_micro >= 0),
        held_micro BIGINT NOT NULL CHECK(held_micro >= 0),
        PRIMARY KEY(owner, id))""")
    )
    conn.execute(
        text("""CREATE TABLE sandbox_reservations (
        owner VARCHAR(80) NOT NULL, id VARCHAR(80) NOT NULL, budget_id VARCHAR(80) NOT NULL,
        request_id VARCHAR(80) NOT NULL, reserved_micro BIGINT NOT NULL CHECK(reserved_micro >= 0),
        actual_micro BIGINT CHECK(actual_micro >= 0),
        state VARCHAR(20) NOT NULL CHECK(state IN ('reserved','uncertain','reconciled')),
        PRIMARY KEY(owner, id), UNIQUE(owner, request_id),
        FOREIGN KEY(owner, budget_id) REFERENCES sandbox_budgets(owner, id))""")
    )
    conn.execute(
        text("""CREATE TABLE application_key_verifiers (
        owner VARCHAR(80) NOT NULL, id VARCHAR(80) NOT NULL, verifier TEXT NOT NULL,
        PRIMARY KEY(owner, id))""")
    )
    conn.execute(
        text("""CREATE TABLE sandbox_payloads (
        owner VARCHAR(80) NOT NULL, kind VARCHAR(40) NOT NULL, id VARCHAR(80) NOT NULL,
        expires_at DOUBLE PRECISION NOT NULL, payload TEXT NOT NULL,
        PRIMARY KEY(owner, kind, id))""")
    )
    conn.execute(text("CREATE INDEX sandbox_payload_expiry ON sandbox_payloads(expires_at)"))
    conn.execute(
        text("""CREATE TABLE sandbox_requests (
        owner VARCHAR(80) NOT NULL, request_key VARCHAR(80) NOT NULL,
        request_id VARCHAR(80) NOT NULL, input_hash VARCHAR(64) NOT NULL,
        state VARCHAR(20) NOT NULL CHECK(state IN ('queued','running','awaiting_approval','succeeded','failed','cancelled','uncertain')),
        PRIMARY KEY(owner,request_key), UNIQUE(owner,request_id))""")
    )
    if dialect == "sqlite":
        for action in ("UPDATE", "DELETE"):
            conn.execute(
                text(
                    f"CREATE TRIGGER immutable_sandbox_{action.lower()} BEFORE {action} ON sandbox_records BEGIN SELECT RAISE(ABORT, 'Sandbox records are immutable'); END"
                )
            )
    else:
        conn.execute(
            text(
                "CREATE TRIGGER immutable_sandbox BEFORE UPDATE OR DELETE ON sandbox_records FOR EACH ROW EXECUTE FUNCTION reject_record_mutation()"
            )
        )


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
