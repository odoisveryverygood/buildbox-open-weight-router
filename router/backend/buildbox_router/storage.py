import time

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import IntegrityError

from .config import Settings
from .contracts import CatalogSnapshot, ErrorCode, ErrorResponse, Job, Recommendation
from .errors import DomainError
from .migrations import REVISION, migrate


def engine_for(settings: Settings) -> Engine:
    settings.prepare_local_directory()
    return create_engine(settings.database_url, pool_pre_ping=True)


class SqlStorage:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def check_revision(self) -> None:
        with self.engine.connect() as conn:
            version = conn.execute(text("SELECT MAX(version) FROM schema_revisions")).scalar()
            if version != REVISION:
                raise RuntimeError("Run the explicit database migration command")

    def put(self, owner: str, kind: str, object_id: str, payload: str, version: int = 1) -> None:
        try:
            with self.engine.begin() as conn:
                existing = conn.execute(
                    text("SELECT owner FROM records WHERE kind=:kind AND id=:id LIMIT 1"),
                    {"kind": kind, "id": object_id},
                ).scalar()
                if existing is not None and existing != owner:
                    raise DomainError(ErrorCode.NOT_FOUND, "Resource not found", 404)
                conn.execute(
                    text(
                        "INSERT INTO records(kind,id,version,owner,payload) VALUES(:kind,:id,:version,:owner,:payload)"
                    ),
                    {
                        "kind": kind,
                        "id": object_id,
                        "version": version,
                        "owner": owner,
                        "payload": payload,
                    },
                )
        except IntegrityError as exc:
            raise DomainError(ErrorCode.CONFLICT, "Immutable version already exists", 409) from exc

    def get(self, owner: str, kind: str, object_id: str, version: int = 1) -> str:
        with self.engine.connect() as conn:
            payload = conn.execute(
                text(
                    "SELECT payload FROM records WHERE kind=:kind AND id=:id AND version=:version AND owner=:owner"
                ),
                {"kind": kind, "id": object_id, "version": version, "owner": owner},
            ).scalar()
            if payload is None:
                raise DomainError(ErrorCode.NOT_FOUND, "Resource not found", 404)
            return str(payload)

    def enqueue(self, owner: str, job: Job) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO jobs(id,owner,status,updated_at,attempts,payload) VALUES(:id,:owner,:status,:updated_at,:attempts,:payload)"
                ),
                {
                    "id": job.id,
                    "owner": owner,
                    "status": job.status,
                    "updated_at": job.updated_at,
                    "attempts": job.attempts,
                    "payload": job.model_dump_json(),
                },
            )

    def job(self, owner: str, job_id: str) -> Job:
        with self.engine.connect() as conn:
            payload = conn.execute(
                text("SELECT payload FROM jobs WHERE id=:id AND owner=:owner"),
                {"id": job_id, "owner": owner},
            ).scalar()
            if payload is None:
                raise DomainError(ErrorCode.NOT_FOUND, "Job not found", 404)
            return Job.model_validate_json(payload)

    def claim(self) -> tuple[str, Job] | None:
        # CAS claim and attempt token prevent stale workers from committing. All work is local.
        now = time.time()
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT * FROM jobs WHERE status='queued' OR (status='running' AND updated_at < :cutoff) ORDER BY updated_at LIMIT 1"
                    ),
                    {"cutoff": now - 60},
                )
                .mappings()
                .first()
            )
            if row is None:
                return None
            old = Job.model_validate_json(row["payload"])
            if old.attempts >= 3:
                exhausted = old.model_copy(
                    update={
                        "status": "failed",
                        "updated_at": now,
                        "error": ErrorResponse(
                            code=ErrorCode.INTERNAL, message="Local job lease retry limit reached"
                        ),
                    }
                )
                conn.execute(
                    text(
                        "UPDATE jobs SET status='failed', updated_at=:now, payload=:payload WHERE id=:id AND attempts=:attempts AND status=:status"
                    ),
                    {
                        "id": old.id,
                        "attempts": old.attempts,
                        "status": old.status,
                        "now": now,
                        "payload": exhausted.model_dump_json(),
                    },
                )
                return None
            claimed = old.model_copy(
                update={"status": "running", "attempts": old.attempts + 1, "updated_at": now}
            )
            result = conn.execute(
                text(
                    "UPDATE jobs SET status='running', updated_at=:now, attempts=:attempts, payload=:payload WHERE id=:id AND status=:old_status AND attempts=:old_attempts"
                ),
                {
                    "id": old.id,
                    "now": now,
                    "attempts": claimed.attempts,
                    "payload": claimed.model_dump_json(),
                    "old_status": old.status,
                    "old_attempts": old.attempts,
                },
            )
            if result.rowcount != 1:
                return None
            return str(row["owner"]), claimed

    def finish(
        self, owner: str, job: Job, recommendation: Recommendation, catalog: CatalogSnapshot
    ) -> None:
        finished = job.model_copy(
            update={
                "status": "succeeded",
                "recommendation_id": recommendation.id,
                "updated_at": time.time(),
            }
        )
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE jobs SET status='succeeded', updated_at=:now, payload=:payload WHERE id=:id AND owner=:owner AND status='running' AND attempts=:attempts"
                ),
                {
                    "id": job.id,
                    "owner": owner,
                    "now": finished.updated_at,
                    "payload": finished.model_dump_json(),
                    "attempts": job.attempts,
                },
            )
            if result.rowcount != 1:
                raise DomainError(ErrorCode.CONFLICT, "Job lease superseded", 409)
            for kind, object_id, payload in (
                ("recommendation", recommendation.id, recommendation.model_dump_json()),
                ("catalog", recommendation.id, catalog.model_dump_json()),
            ):
                conn.execute(
                    text(
                        "INSERT INTO records(kind,id,version,owner,payload) VALUES(:kind,:id,1,:owner,:payload)"
                    ),
                    {"kind": kind, "id": object_id, "owner": owner, "payload": payload},
                )

    def fail(self, owner: str, job: Job) -> None:
        failed = job.model_copy(
            update={
                "status": "failed",
                "updated_at": time.time(),
                "error": ErrorResponse(
                    code=ErrorCode.INTERNAL,
                    message="Offline job failed; inspect local tests, then submit a new job",
                ),
            }
        )
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE jobs SET status='failed', updated_at=:now, payload=:payload WHERE id=:id AND owner=:owner AND status='running' AND attempts=:attempts"
                ),
                {
                    "id": job.id,
                    "owner": owner,
                    "now": failed.updated_at,
                    "payload": failed.model_dump_json(),
                    "attempts": job.attempts,
                },
            )


if __name__ == "__main__":
    engine = engine_for(Settings.from_env())
    migrate(engine)
    engine.dispose()
    print("Schema revision 1 ready")
