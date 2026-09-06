"""Integration-owned transactions: versioned submissions, progress, cancellation and cost holds."""

import hashlib
import json
import time
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from .contracts import ErrorCode, ErrorResponse, Job
from .errors import DomainError
from .planning_contracts import PlanInput, PlanningResult, PlanVersion, PlanView
from .storage import SqlStorage


class PlanningStorage(SqlStorage):
    def submit(
        self,
        owner: str,
        key: str,
        value: PlanInput,
        plan_id: str | None = None,
        prior: int | None = None,
    ) -> PlanView:
        raw = value.model_dump_json()
        digest = hashlib.sha256(
            json.dumps(
                {"input": json.loads(raw), "id": plan_id, "prior": prior}, sort_keys=True
            ).encode()
        ).hexdigest()
        try:
            with self.engine.begin() as conn:
                old = (
                    conn.execute(
                        text("SELECT * FROM submissions WHERE owner=:owner AND request_key=:key"),
                        {"owner": owner, "key": key},
                    )
                    .mappings()
                    .first()
                )
                if old:
                    if old["input_hash"] != digest:
                        raise DomainError(
                            ErrorCode.CONFLICT,
                            "Idempotency key already binds a different request",
                            409,
                        )
                    chosen_id, version = old["plan_id"], old["version"]
                else:
                    if (
                        conn.execute(
                            text(
                                "SELECT count(*) FROM jobs WHERE owner=:owner AND status IN ('queued','running')"
                            ),
                            {"owner": owner},
                        ).scalar_one()
                        >= 4
                    ):
                        raise DomainError(ErrorCode.CONFLICT, "Pending-job quota reached", 429)
                    chosen_id, version = plan_id or uuid4().hex, 1
                    if plan_id is not None:
                        latest = conn.execute(
                            text(
                                "SELECT MAX(version) FROM records WHERE kind='plan' AND id=:id AND owner=:owner"
                            ),
                            {"id": plan_id, "owner": owner},
                        ).scalar()
                        if latest is None:
                            raise DomainError(ErrorCode.NOT_FOUND, "Plan not found", 404)
                        if latest != prior:
                            raise DomainError(
                                ErrorCode.CONFLICT,
                                "Plan changed; reload the exact latest version",
                                409,
                            )
                        version = latest + 1
                    if value.edited_workflow and (
                        value.edited_workflow.id != chosen_id
                        or value.edited_workflow.version != version
                    ):
                        raise DomainError(
                            ErrorCode.INVALID,
                            "Edited workflow must bind the new exact plan version",
                            422,
                        )
                    plan = PlanVersion(
                        id=chosen_id, version=version, input=value, input_hash=digest
                    )
                    now = time.time()
                    job = Job(
                        id=uuid4().hex,
                        workflow_id=chosen_id,
                        workflow_version=version,
                        status="queued",
                        operation="planning",
                        created_at=now,
                        updated_at=now,
                    )
                    conn.execute(
                        text(
                            "INSERT INTO records(kind,id,version,owner,payload) VALUES('plan',:id,:version,:owner,:payload)"
                        ),
                        {
                            "id": chosen_id,
                            "version": version,
                            "owner": owner,
                            "payload": plan.model_dump_json(),
                        },
                    )
                    conn.execute(
                        text(
                            "INSERT INTO jobs(id,owner,status,updated_at,attempts,payload) VALUES(:id,:owner,'queued',:now,0,:payload)"
                        ),
                        {
                            "id": job.id,
                            "owner": owner,
                            "now": now,
                            "payload": job.model_dump_json(),
                        },
                    )
                    conn.execute(
                        text("INSERT INTO submissions VALUES(:owner,:key,:hash,:id,:version,:job)"),
                        {
                            "owner": owner,
                            "key": key,
                            "hash": digest,
                            "id": chosen_id,
                            "version": version,
                            "job": job.id,
                        },
                    )
        except IntegrityError:
            raise DomainError(
                ErrorCode.CONFLICT,
                "Concurrent submission; reload before retrying the same key",
                409,
            ) from None
        return self.view(owner, chosen_id, version)

    def view(self, owner: str, plan_id: str, version: int) -> PlanView:
        plan = PlanVersion.model_validate_json(self.get(owner, "plan", plan_id, version))
        with self.engine.connect() as conn:
            latest = conn.execute(
                text(
                    "SELECT MAX(version) FROM records WHERE kind='plan' AND id=:id AND owner=:owner"
                ),
                {"id": plan_id, "owner": owner},
            ).scalar_one()
            job_id = conn.execute(
                text(
                    "SELECT job_id FROM submissions WHERE owner=:owner AND plan_id=:id AND version=:version"
                ),
                {"owner": owner, "id": plan_id, "version": version},
            ).scalar_one()
        job = self.job(owner, job_id)
        result = (
            PlanningResult.model_validate_json(self.get(owner, "planning_result", job.id))
            if job.status == "succeeded"
            else None
        )
        return PlanView(
            plan=plan, latest_version=latest, stale=version != latest, job=job, result=result
        )

    def update_job(self, owner: str, job: Job, **changes: object) -> Job:
        updated = Job.model_validate({**job.model_dump(), **changes, "updated_at": time.time()})
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE jobs SET status=:status, updated_at=:now, payload=:payload WHERE id=:id AND owner=:owner AND status=:old AND attempts=:attempts"
                ),
                {
                    "id": job.id,
                    "owner": owner,
                    "old": job.status,
                    "attempts": job.attempts,
                    "status": updated.status,
                    "now": updated.updated_at,
                    "payload": updated.model_dump_json(),
                },
            )
            if result.rowcount != 1:
                raise DomainError(ErrorCode.CONFLICT, "Job cancelled or lease superseded", 409)
        return updated

    def cancel(self, owner: str, plan_id: str, version: int) -> PlanView:
        view = self.view(owner, plan_id, version)
        if view.job.status in ("queued", "running"):
            self.update_job(
                owner,
                view.job,
                status="cancelled",
                phase="cancelled",
                accounting="uncertain"
                if view.job.accounting == "reserved"
                else view.job.accounting,
            )
        return self.view(owner, plan_id, version)

    def complete_planning(self, owner: str, job: Job, value: PlanningResult) -> None:
        if (value.plan_id, value.version) != (job.workflow_id, job.workflow_version):
            raise DomainError(ErrorCode.CONFLICT, "Result version mismatch", 409)
        finished = job.model_copy(
            update={"status": "succeeded", "phase": value.status, "updated_at": time.time()}
        )
        rows = [("planning_result", job.id, 1, value.model_dump_json())]
        if value.workflow:
            rows.append(
                (
                    "workflow",
                    value.workflow.id,
                    value.workflow.version,
                    value.workflow.model_dump_json(),
                )
            )
        if value.recommendation and value.catalog:
            rows.extend(
                [
                    (
                        "recommendation",
                        value.recommendation.id,
                        1,
                        value.recommendation.model_dump_json(),
                    ),
                    ("catalog", value.recommendation.id, 1, value.catalog.model_dump_json()),
                ]
            )
        with self.engine.begin() as conn:
            changed = conn.execute(
                text(
                    "UPDATE jobs SET status='succeeded', updated_at=:now,payload=:payload WHERE id=:id AND owner=:owner AND status='running' AND attempts=:attempts"
                ),
                {
                    "id": job.id,
                    "owner": owner,
                    "attempts": job.attempts,
                    "now": finished.updated_at,
                    "payload": finished.model_dump_json(),
                },
            )
            if changed.rowcount != 1:
                raise DomainError(ErrorCode.CONFLICT, "Job cancelled or lease superseded", 409)
            for kind, identifier, version, payload in rows:
                conn.execute(
                    text(
                        "INSERT INTO records(kind,id,version,owner,payload) VALUES(:kind,:id,:version,:owner,:payload)"
                    ),
                    {
                        "kind": kind,
                        "id": identifier,
                        "version": version,
                        "owner": owner,
                        "payload": payload,
                    },
                )

    def reserve_call(
        self,
        owner: str,
        job: Job,
        role: str,
        approval: str,
        reserve_micro: int,
        cap_micro: int,
        candidate_cap_micro: int | None = None,
    ) -> str:
        if reserve_micro <= 0 or cap_micro < reserve_micro:
            raise DomainError(ErrorCode.UNSUPPORTED, "Paid-call budget approval is missing")
        # Claim/lock the job before checking its budget: portable across SQLite/PostgreSQL.
        identifier = uuid4().hex
        with self.engine.begin() as conn:
            locked = conn.execute(
                text(
                    "UPDATE jobs SET attempts=attempts WHERE id=:id AND owner=:owner AND status='running' AND attempts=:attempts"
                ),
                {"id": job.id, "owner": owner, "attempts": job.attempts},
            )
            if locked.rowcount != 1:
                raise DomainError(ErrorCode.CONFLICT, "Job no longer authorized", 409)
            candidate_used = conn.execute(
                text(
                    "SELECT COALESCE(SUM(reserved_micro),0) FROM provider_calls WHERE owner=:owner AND job_id=:id"
                ),
                {"owner": owner, "id": job.id},
            ).scalar_one()
            if candidate_used + reserve_micro > (
                candidate_cap_micro if candidate_cap_micro is not None else cap_micro
            ):
                raise DomainError(ErrorCode.UNSUPPORTED, "Candidate planning budget exhausted")
            conn.execute(
                text("INSERT INTO approval_budgets VALUES(:id,:cap,0) ON CONFLICT(id) DO NOTHING"),
                {"id": approval, "cap": cap_micro},
            )
            held = conn.execute(
                text(
                    "UPDATE approval_budgets SET held_micro=held_micro+:reserve WHERE id=:id AND cap_micro=:cap AND held_micro+:reserve<=cap_micro"
                ),
                {"id": approval, "cap": cap_micro, "reserve": reserve_micro},
            )
            if held.rowcount != 1:
                raise DomainError(ErrorCode.UNSUPPORTED, "Recorded approval budget exhausted")
            conn.execute(
                text(
                    "INSERT INTO provider_calls VALUES(:id,:owner,:job,:role,:approval,'reserved',:reserved,NULL,'{}')"
                ),
                {
                    "id": identifier,
                    "owner": owner,
                    "job": job.id,
                    "role": role,
                    "approval": approval,
                    "reserved": reserve_micro,
                },
            )
        return identifier

    def settle_call(
        self, identifier: str, actual_micro: int | None, metadata: dict[str, object]
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE provider_calls SET state=:state, actual_micro=:actual,metadata=:metadata WHERE id=:id AND state='reserved'"
                ),
                {
                    "id": identifier,
                    "state": "known" if actual_micro is not None else "uncertain",
                    "actual": actual_micro,
                    "metadata": json.dumps(metadata),
                },
            )

    def has_uncertain_call(self, owner: str, job: Job) -> bool:
        with self.engine.connect() as conn:
            return bool(
                conn.execute(
                    text(
                        "SELECT count(*) FROM provider_calls WHERE owner=:owner AND job_id=:id AND state IN ('reserved','uncertain')"
                    ),
                    {"owner": owner, "id": job.id},
                ).scalar_one()
            )

    def safe_failure(self, owner: str, job: Job, message: str, uncertain: bool = False) -> None:
        self.update_job(
            owner,
            job,
            status="uncertain" if uncertain else "failed",
            phase="requires_reconciliation" if uncertain else "failed",
            error=ErrorResponse(code=ErrorCode.UNSUPPORTED, message=message),
            accounting="uncertain" if uncertain else job.accounting,
        )
