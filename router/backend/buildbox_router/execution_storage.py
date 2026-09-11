"""Integration-owned sandbox persistence and atomic state/budget primitives.

No automatic migration, execution, key creation, grant issuance, or paid calls.
Admission provisioning is operator-only and deliberately has no HTTP endpoint.
"""

import hashlib
import re
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

from pydantic import TypeAdapter
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from .contracts import ErrorCode
from .errors import DomainError
from .execution_contracts import (
    ApplicationKeyMetadata,
    ComparisonResult,
    DecisionTrace,
    ExecutablePolicy,
    ExecutionContract,
    ImportedSample,
    PolicyTransition,
    PolicyView,
    PromptRevision,
    RouteAlias,
    RunAttempt,
    RunEvent,
    SandboxAdmission,
    SandboxRun,
    StoredOutput,
    TransitionRequest,
    VersionRef,
    WorkflowRunRequest,
)
from .execution_security import validate_admission, validate_alias
from .planning_storage import PlanningStorage
from .runtime_contracts import QueuedContext
from .storage import SqlStorage


def state_id(ref: VersionRef) -> str:
    return hashlib.sha256(f"{ref.id}:{ref.version}".encode()).hexdigest()


def append(
    conn: Connection,
    tenant: str,
    kind: str,
    identifier: str,
    version: int,
    value: ExecutionContract,
) -> None:
    params = dict(
        owner=tenant, kind=kind, id=identifier, version=version, payload=value.model_dump_json()
    )
    old = conn.execute(
        text(
            "SELECT payload FROM sandbox_records WHERE owner=:owner AND kind=:kind AND id=:id AND version=:version"
        ),
        params,
    ).scalar()
    if old is not None:
        if old == params["payload"]:
            return
        raise DomainError(ErrorCode.CONFLICT, "Immutable sandbox record already exists", 409)
    conn.execute(
        text(
            "INSERT INTO sandbox_records(owner,kind,id,version,payload) VALUES(:owner,:kind,:id,:version,:payload)"
        ),
        params,
    )


class SandboxStorage(SqlStorage):
    def __init__(self, engine: Engine, *, offline_contract_test: bool = False) -> None:
        super().__init__(engine)
        self.offline_contract_test = offline_contract_test

    def records(self, tenant: str, kind: str) -> tuple[str, ...]:
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT r.payload FROM sandbox_records r WHERE r.owner=:owner AND r.kind=:kind AND r.version=(SELECT MAX(s.version) FROM sandbox_records s WHERE s.owner=r.owner AND s.kind=r.kind AND s.id=r.id) ORDER BY r.id LIMIT 1000"
                    ),
                    dict(owner=tenant, kind=kind),
                )
                .scalars()
                .all()
            )
        return tuple(str(v) for v in rows)

    def enqueue_runtime(
        self, context: QueuedContext, value: WorkflowRunRequest, run: SandboxRun, input_hash: str
    ) -> tuple[str, bool]:
        now = datetime.now(UTC)
        with self.engine.begin() as conn:
            identifier, created = self.register_request(
                context.tenant_id, context.idempotency_key, run.id, input_hash, connection=conn
            )
            if not created:
                return identifier, False
            append(conn, context.tenant_id, "run", run.id, 1, run)
            append(conn, context.tenant_id, "queued_context", run.id, 1, context)
            conn.execute(
                text(
                    "INSERT INTO sandbox_payloads(owner,kind,id,expires_at,payload) VALUES(:owner,'queued_input',:id,:expires,:payload)"
                ),
                dict(
                    owner=context.tenant_id,
                    id=run.id,
                    expires=(now + timedelta(seconds=120)).timestamp(),
                    payload=value.model_dump_json(),
                ),
            )

            conn.execute(
                text(
                    "INSERT INTO runtime_queue(owner,id,request_key,principal_id,key_id,deadline,state) VALUES(:owner,:id,:key,:principal,:key_id,:deadline,'queued')"
                ),
                dict(
                    owner=context.tenant_id,
                    id=run.id,
                    key=context.idempotency_key,
                    principal=context.principal_id,
                    key_id=context.application_key.id if context.application_key else None,
                    deadline=context.deadline.timestamp(),
                ),
            )
        return run.id, True

    def attempts(self, tenant: str, run_id: str) -> tuple[RunAttempt, ...]:
        # Filter before the list bound, so older workspace activity cannot hide
        # the attempts/costs of the specifically authorized run being inspected.
        field = (
            "json_extract(r.payload,'$.run_id')"
            if self.engine.dialect.name == "sqlite"
            else "CAST(r.payload AS jsonb)->>'run_id'"
        )
        with self.engine.connect() as conn:
            values = (
                conn.execute(
                    text(
                        f"SELECT r.payload FROM sandbox_records r WHERE r.owner=:owner AND r.kind='attempt' AND {field}=:run AND r.version=(SELECT MAX(s.version) FROM sandbox_records s WHERE s.owner=r.owner AND s.kind=r.kind AND s.id=r.id) ORDER BY r.id LIMIT 1000"
                    ),
                    dict(owner=tenant, run=run_id),
                )
                .scalars()
                .all()
            )
        return tuple(RunAttempt.model_validate_json(v) for v in values)

    def outputs_for_run(self, tenant: str, run_id: str) -> tuple[StoredOutput, ...]:
        field = (
            "json_extract(payload,'$.run_id')"
            if self.engine.dialect.name == "sqlite"
            else "CAST(payload AS jsonb)->>'run_id'"
        )
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        f"SELECT payload FROM sandbox_payloads WHERE owner=:owner AND kind='output' AND {field}=:run AND expires_at>:now ORDER BY id LIMIT 1000"
                    ),
                    dict(owner=tenant, run=run_id, now=datetime.now(UTC).timestamp()),
                )
                .scalars()
                .all()
            )
        return tuple(StoredOutput.model_validate_json(row) for row in rows)

    def claim_runtime(self) -> tuple[QueuedContext, WorkflowRunRequest] | None:
        now = datetime.now(UTC).timestamp()
        with self.engine.begin() as conn:
            conn.execute(
                text("DELETE FROM sandbox_payloads WHERE kind='queued_input' AND expires_at<=:now"),
                dict(now=now),
            )
            # A lease expiry is uncertainty, never permission to redispatch.
            expired = conn.execute(
                text(
                    "SELECT owner,id FROM runtime_queue WHERE (state='running' AND lease_until<:now) OR (state='queued' AND deadline<:now)"
                ),
                dict(now=now),
            ).all()
            for owner, identifier in expired:
                conn.execute(
                    text(
                        "UPDATE runtime_queue SET state='uncertain' WHERE owner=:owner AND id=:id"
                    ),
                    dict(owner=owner, id=identifier),
                )
                conn.execute(
                    text(
                        "UPDATE sandbox_requests SET state='uncertain' WHERE owner=:owner AND request_id=:id AND state IN ('queued','running')"
                    ),
                    dict(owner=owner, id=identifier),
                )
            rows = conn.execute(
                text(
                    "SELECT owner,id FROM runtime_queue WHERE state='queued' AND deadline>:now ORDER BY deadline LIMIT 20"
                ),
                dict(now=now),
            ).all()
            selected = None
            for owner, identifier in rows:
                result = conn.execute(
                    text(
                        "UPDATE runtime_queue SET state='running',lease_until=:lease WHERE owner=:owner AND id=:id AND state='queued'"
                    ),
                    dict(owner=owner, id=identifier, lease=now + 125),
                )
                if result.rowcount == 1:
                    selected = str(owner), str(identifier)
                    break
        if selected is None:
            return None
        tenant, identifier = selected
        try:
            return (
                QueuedContext.model_validate_json(self.read(tenant, "queued_context", identifier)),
                WorkflowRunRequest.model_validate_json(
                    self._read_payload(tenant, "queued_input", identifier)
                ),
            )
        except DomainError:
            self.finish_runtime(tenant, identifier, uncertain=True)
            return None

    def queue_claimed(self, tenant: str, identifier: str) -> bool:
        with self.engine.connect() as conn:
            return (
                conn.execute(
                    text("SELECT state FROM runtime_queue WHERE owner=:owner AND id=:id"),
                    dict(owner=tenant, id=identifier),
                ).scalar()
                == "running"
            )

    def finish_runtime(self, tenant: str, identifier: str, *, uncertain: bool = False) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE runtime_queue SET state=:state WHERE owner=:owner AND id=:id AND state='running'"
                ),
                dict(owner=tenant, id=identifier, state="uncertain" if uncertain else "done"),
            )
            if uncertain:
                conn.execute(
                    text(
                        "UPDATE sandbox_requests SET state='uncertain' WHERE owner=:owner AND request_id=:id AND state IN ('running','queued')"
                    ),
                    dict(owner=tenant, id=identifier),
                )
            conn.execute(
                text(
                    "DELETE FROM sandbox_payloads WHERE owner=:owner AND id=:id AND kind='queued_input'"
                ),
                dict(owner=tenant, id=identifier),
            )

    def request_state(self, tenant: str, request_id: str) -> str:
        with self.engine.connect() as conn:
            state = conn.execute(
                text("SELECT state FROM sandbox_requests WHERE owner=:owner AND request_id=:id"),
                dict(owner=tenant, id=request_id),
            ).scalar()
        if state is None:
            raise DomainError(ErrorCode.NOT_FOUND, "Request not found", 404)
        return str(state)

    def advance_request(self, tenant: str, request_id: str, expected: str, state: str) -> None:
        transitions = {
            "queued": {"running", "cancelled"},
            "running": {"succeeded", "failed", "cancelled", "uncertain", "awaiting_approval"},
        }
        if state not in transitions.get(expected, set()):
            raise DomainError(ErrorCode.CONFLICT, "Invalid runtime request transition", 409)
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE sandbox_requests SET state=:state WHERE owner=:owner AND request_id=:id AND state=:expected"
                ),
                dict(owner=tenant, id=request_id, state=state, expected=expected),
            )
            if result.rowcount != 1:
                raise DomainError(
                    ErrorCode.CONFLICT, "Request state changed; do not redispatch", 409
                )

    def latest(self, tenant: str, kind: str, identifier: str) -> tuple[int, str]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT version,payload FROM sandbox_records WHERE owner=:owner AND kind=:kind AND id=:id ORDER BY version DESC LIMIT 1"
                ),
                dict(owner=tenant, kind=kind, id=identifier),
            ).first()
        if row is None:
            raise DomainError(ErrorCode.NOT_FOUND, "Sandbox resource not found", 404)
        return int(row[0]), str(row[1])

    def save_event(self, tenant: str, value: RunEvent) -> None:
        TypeAdapter(RunEvent).validate_json(value.model_dump_json())
        self.latest(tenant, "run", value.run_id)
        with self.engine.begin() as conn:
            latest = (
                conn.execute(
                    text(
                        "SELECT MAX(version) FROM sandbox_records WHERE owner=:owner AND kind='run_event' AND id=:id"
                    ),
                    dict(owner=tenant, id=value.run_id),
                ).scalar()
                or 0
            )
            if value.sequence != latest + 1:
                raise DomainError(ErrorCode.CONFLICT, "Event sequence must be next", 409)
            append(conn, tenant, "run_event", value.run_id, value.sequence, value)

    def events(self, tenant: str, run_id: str, after_sequence: int) -> tuple[RunEvent, ...]:
        self.latest(tenant, "run", run_id)
        if not 0 <= after_sequence <= 10000:
            raise DomainError(ErrorCode.INVALID, "Invalid event cursor", 422)
        with self.engine.connect() as conn:
            rows = (
                conn.execute(
                    text(
                        "SELECT payload FROM sandbox_records WHERE owner=:owner AND kind='run_event' AND id=:id AND version>:after ORDER BY version LIMIT 1000"
                    ),
                    dict(owner=tenant, id=run_id, after=after_sequence),
                )
                .scalars()
                .all()
            )
        return tuple(TypeAdapter(RunEvent).validate_json(str(raw)) for raw in rows)

    def save_application_key(
        self,
        tenant: str,
        value: ApplicationKeyMetadata,
        verifier: str,
        *,
        cap_micro: int | None = None,
    ) -> None:
        """Lane 7 supplies an independently issued random secret's verifier, never raw key."""
        if value.tenant_id != tenant or not re.fullmatch(
            r"pbkdf2_sha256:[1-9][0-9]{5,6}:[a-f0-9]{32}:[a-f0-9]{64}", verifier
        ):
            raise ValueError("Tenant or key verifier format denied")
        try:
            with self.engine.begin() as conn:
                if cap_micro is not None:
                    self.provision_budget(tenant, "key-" + value.id, cap_micro, connection=conn)
                append(conn, tenant, "application_key", value.id, 1, value)
                conn.execute(
                    text(
                        "INSERT INTO application_key_verifiers(owner,id,verifier) VALUES(:owner,:id,:verifier)"
                    ),
                    dict(owner=tenant, id=value.id, verifier=verifier),
                )
        except IntegrityError:
            raise DomainError(ErrorCode.CONFLICT, "Key ID already issued", 409) from None

    def key_record(self, tenant: str, key_id: str) -> tuple[ApplicationKeyMetadata, str]:
        """Private auth adapter only; no route exposes verifier material."""
        _, raw = self.latest(tenant, "application_key", key_id)
        with self.engine.connect() as conn:
            verifier = conn.execute(
                text(
                    "SELECT verifier FROM application_key_verifiers WHERE owner=:owner AND id=:id"
                ),
                dict(owner=tenant, id=key_id),
            ).scalar_one()
        return ApplicationKeyMetadata.model_validate_json(raw), str(verifier)

    def revoke_key(self, tenant: str, key_id: str, now: datetime) -> ApplicationKeyMetadata:
        version, raw = self.latest(tenant, "application_key", key_id)
        value = ApplicationKeyMetadata.model_validate_json(raw)
        if value.revoked_at is not None:
            return value
        value = ApplicationKeyMetadata.model_validate(value.model_dump() | {"revoked_at": now})
        try:
            with self.engine.begin() as conn:
                append(conn, tenant, "application_key", key_id, version + 1, value)
        except IntegrityError:
            raise DomainError(
                ErrorCode.CONFLICT, "Concurrent key revocation; reread", 409
            ) from None
        return value

    def register_request(
        self,
        tenant: str,
        key: str,
        request_id: str,
        input_hash: str,
        *,
        connection: Connection | None = None,
    ) -> tuple[str, bool]:
        """Persist before dispatch. True=created; False=return saved run, never redispatch."""
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", key) or not re.fullmatch(
            r"[a-f0-9]{64}", input_hash
        ):
            raise DomainError(ErrorCode.INVALID, "Invalid idempotency key or digest", 422)
        try:
            with nullcontext(connection) if connection is not None else self.engine.begin() as conn:
                row = (
                    conn.execute(
                        text(
                            "SELECT request_id,input_hash FROM sandbox_requests WHERE owner=:owner AND request_key=:key"
                        ),
                        dict(owner=tenant, key=key),
                    )
                    .mappings()
                    .first()
                )
                if row:
                    if row["input_hash"] != input_hash:
                        raise DomainError(
                            ErrorCode.CONFLICT, "Idempotency key binds different content", 409
                        )
                    return str(row["request_id"]), False
                conn.execute(
                    text(
                        "INSERT INTO sandbox_requests(owner,request_key,request_id,input_hash,state) VALUES(:owner,:key,:request,:hash,'queued')"
                    ),
                    dict(owner=tenant, key=key, request=request_id, hash=input_hash),
                )
                return request_id, True
        except IntegrityError:
            raise DomainError(
                ErrorCode.CONFLICT, "Concurrent request registration; reread same key", 409
            ) from None

    def read(self, tenant: str, kind: str, identifier: str, version: int = 1) -> str:
        with self.engine.connect() as conn:
            value = conn.execute(
                text(
                    "SELECT payload FROM sandbox_records WHERE owner=:owner AND kind=:kind AND id=:id AND version=:version"
                ),
                dict(owner=tenant, kind=kind, id=identifier, version=version),
            ).scalar()
        if value is None:
            raise DomainError(ErrorCode.NOT_FOUND, "Sandbox resource not found", 404)
        return str(value)

    def create_policy(self, tenant: str, value: ExecutablePolicy) -> PolicyView:
        view = PlanningStorage(self.engine).view(tenant, value.plan.id, value.plan.version)
        if (
            not view.result
            or value.workflow != view.result.workflow
            or not view.result.catalog
            or value.catalog_id != view.result.catalog.id
        ):
            raise DomainError(
                ErrorCode.CONFLICT,
                "Policy must preserve an owned saved workflow and its pinned catalog; edit/replan first",
                409,
            )
        configs = {c.id for c in view.result.catalog.configurations}
        if any(
            c not in configs
            for s in value.stages
            for c in ((s.configuration_id,) if s.configuration_id else ())
            + s.fallback_configuration_ids
        ):
            raise DomainError(ErrorCode.INVALID, "Configuration is not in the pinned catalog", 422)
        return self._append_policy(tenant, value)

    def _append_policy(self, tenant: str, value: ExecutablePolicy) -> PolicyView:
        """Internal primitive; public composition must call create_policy."""
        ref = VersionRef(id=value.id, version=value.version)
        try:
            with self.engine.begin() as conn:
                latest = (
                    conn.execute(
                        text(
                            "SELECT MAX(version) FROM sandbox_records WHERE owner=:owner AND kind='policy' AND id=:id"
                        ),
                        dict(owner=tenant, id=value.id),
                    ).scalar()
                    or 0
                )
                if value.version > latest + 1:
                    raise DomainError(ErrorCode.CONFLICT, "Policy revision must be sequential", 409)
                append(conn, tenant, "policy", value.id, value.version, value)
                if value.version == latest + 1:
                    transition = PolicyTransition(
                        policy=ref,
                        sequence=1,
                        status="draft",
                        actor_id=tenant,
                        occurred_at=datetime.now(UTC),
                    )
                    append(conn, tenant, "transition", state_id(ref), 1, transition)
                    conn.execute(
                        text(
                            "INSERT INTO sandbox_heads(owner,policy_id,policy_version,sequence) VALUES(:owner,:id,:version,1)"
                        ),
                        dict(owner=tenant, id=value.id, version=value.version),
                    )
        except IntegrityError:
            raise DomainError(
                ErrorCode.CONFLICT, "Concurrent policy creation; reload", 409
            ) from None
        return self.policy(tenant, ref)

    def policy(self, tenant: str, ref: VersionRef) -> PolicyView:
        value = ExecutablePolicy.model_validate_json(
            self.read(tenant, "policy", ref.id, ref.version)
        )
        with self.engine.connect() as conn:
            sequence = conn.execute(
                text(
                    "SELECT sequence FROM sandbox_heads WHERE owner=:owner AND policy_id=:id AND policy_version=:version"
                ),
                dict(owner=tenant, id=ref.id, version=ref.version),
            ).scalar_one()
        transition = PolicyTransition.model_validate_json(
            self.read(tenant, "transition", state_id(ref), sequence)
        )
        return PolicyView(policy=value, transition=transition)

    def policy_exists(self, tenant: str, policy: VersionRef) -> bool:
        try:
            self.policy(tenant, policy)
            return True
        except DomainError as exc:
            if exc.status == 404:
                return False
            raise

    def transition(self, tenant: str, ref: VersionRef, request: TransitionRequest) -> PolicyView:
        view = self.policy(tenant, ref)
        if (
            view.transition.sequence != request.expected_sequence
            or request.status == view.transition.status
        ):
            raise DomainError(
                ErrorCode.CONFLICT, "Transition is stale or does not change state", 409
            )
        if request.status == "sandbox_enabled":
            if not request.admission_id:
                raise DomainError(ErrorCode.UNSUPPORTED, "Sandbox admission required", 403)
            admission = SandboxAdmission.model_validate_json(
                self.read(tenant, "admission", request.admission_id)
            )
            validate_admission(
                tenant,
                view.policy,
                admission,
                datetime.now(UTC),
                allow_synthetic=self.offline_contract_test,
            )
        elif request.admission_id is not None:
            raise DomainError(
                ErrorCode.INVALID, "Disabled transitions cannot attach an admission", 422
            )
        value = PolicyTransition(
            policy=ref,
            sequence=request.expected_sequence + 1,
            status=request.status,
            admission_id=request.admission_id,
            actor_id=tenant,
            occurred_at=datetime.now(UTC),
        )
        with self.engine.begin() as conn:
            result = conn.execute(
                text(
                    "UPDATE sandbox_heads SET sequence=:next WHERE owner=:owner AND policy_id=:id AND policy_version=:version AND sequence=:prior"
                ),
                dict(
                    owner=tenant,
                    id=ref.id,
                    version=ref.version,
                    prior=request.expected_sequence,
                    next=value.sequence,
                ),
            )
            if result.rowcount != 1:
                raise DomainError(ErrorCode.CONFLICT, "Concurrent transition; reload", 409)
            append(conn, tenant, "transition", state_id(ref), value.sequence, value)
        return self.policy(tenant, ref)

    def create_alias(self, tenant: str, value: RouteAlias) -> RouteAlias:
        validate_alias(self.policy(tenant, value.policy).policy, value)
        try:
            with self.engine.begin() as conn:
                append(conn, tenant, "alias", value.id, 1, value)
        except IntegrityError:
            raise DomainError(ErrorCode.CONFLICT, "Alias already pinned", 409) from None
        return value

    def alias(self, tenant: str, alias_id: str) -> RouteAlias:
        return RouteAlias.model_validate_json(self.read(tenant, "alias", alias_id))

    def import_sample(self, tenant: str, value: ImportedSample) -> ImportedSample:
        if abs((datetime.now(UTC) - value.imported_at).total_seconds()) > 60:
            raise DomainError(ErrorCode.INVALID, "Import time must be assigned by the server", 422)
        self._payload(
            tenant,
            "sample",
            value.id,
            value,
            value.imported_at + timedelta(days=value.retention_days),
        )
        return value

    def sample(self, tenant: str, sample_id: str) -> ImportedSample:
        return ImportedSample.model_validate_json(self._read_payload(tenant, "sample", sample_id))

    def _payload(
        self, tenant: str, kind: str, identifier: str, value: ExecutionContract, expiry: datetime
    ) -> None:
        raw = value.model_dump_json()
        if len(raw.encode()) > 65536:
            raise DomainError(ErrorCode.INVALID, "Payload exceeds 64 KiB", 413)
        try:
            with self.engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO sandbox_payloads(owner,kind,id,expires_at,payload) VALUES(:owner,:kind,:id,:expires,:payload)"
                    ),
                    dict(
                        owner=tenant,
                        kind=kind,
                        id=identifier,
                        expires=expiry.timestamp(),
                        payload=raw,
                    ),
                )
        except IntegrityError:
            raise DomainError(ErrorCode.CONFLICT, "Payload ID already exists", 409) from None

    def _read_payload(self, tenant: str, kind: str, identifier: str) -> str:
        with self.engine.connect() as conn:
            raw = conn.execute(
                text(
                    "SELECT payload FROM sandbox_payloads WHERE owner=:owner AND kind=:kind AND id=:id AND expires_at>:now"
                ),
                dict(owner=tenant, kind=kind, id=identifier, now=datetime.now(UTC).timestamp()),
            ).scalar()
        if raw is None:
            raise DomainError(ErrorCode.NOT_FOUND, "Payload not found or expired", 404)
        return str(raw)

    def purge_expired_payloads(self, now: datetime) -> int:
        """Explicit maintenance deletes only expired private payloads, not audit metadata."""
        with self.engine.begin() as conn:
            return int(
                conn.execute(
                    text("DELETE FROM sandbox_payloads WHERE expires_at<=:now"),
                    dict(now=now.timestamp()),
                ).rowcount
            )

    def save_output(self, tenant: str, value: StoredOutput) -> None:
        self._payload(tenant, "output", value.id, value, value.expires_at)

    def output(self, tenant: str, identifier: str) -> StoredOutput:
        return StoredOutput.model_validate_json(self._read_payload(tenant, "output", identifier))

    def save_prompt(self, tenant: str, value: PromptRevision) -> PromptRevision:
        if value.parent:
            self.read(tenant, "prompt", value.parent.id, value.parent.version)
        with self.engine.begin() as conn:
            append(conn, tenant, "prompt", value.id, value.version, value)
        return value

    def save_run(self, tenant: str, value: SandboxRun, revision: int) -> None:
        with self.engine.begin() as conn:
            append(conn, tenant, "run", value.id, revision, value)

    def save_attempt(self, tenant: str, value: RunAttempt, revision: int) -> None:
        if value.trace.tenant_id != tenant:
            raise DomainError(ErrorCode.NOT_FOUND, "Attempt tenant mismatch", 404)
        with self.engine.begin() as conn:
            append(conn, tenant, "attempt", value.id, revision, value)

    def save_trace(self, tenant: str, value: DecisionTrace) -> None:
        if value.tenant_id != tenant:
            raise DomainError(ErrorCode.NOT_FOUND, "Trace tenant mismatch", 404)
        with self.engine.begin() as conn:
            append(conn, tenant, "trace", value.request_id, 1, value)

    def save_comparison(self, tenant: str, value: ComparisonResult, revision: int) -> None:
        with self.engine.begin() as conn:
            append(conn, tenant, "comparison", value.id, revision, value)

    def trace(self, tenant: str, request_id: str) -> DecisionTrace:
        return DecisionTrace.model_validate_json(self.read(tenant, "trace", request_id))

    def provision_budget(
        self, tenant: str, identifier: str, cap_micro: int, *, connection: Connection | None = None
    ) -> None:
        """Operator-only. Existing caps are immutable, not increased by request fields."""
        if type(cap_micro) is not int or not 0 <= cap_micro <= 1_000_000:
            raise ValueError("Invalid approved sandbox cap")
        with nullcontext(connection) if connection is not None else self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO sandbox_budgets(owner,id,cap_micro,held_micro) VALUES(:owner,:id,:cap,0)"
                ),
                dict(owner=tenant, id=identifier, cap=cap_micro),
            )

    def budget_cap(self, tenant: str, identifier: str) -> int:
        with self.engine.connect() as conn:
            value = conn.execute(
                text("SELECT cap_micro FROM sandbox_budgets WHERE owner=:owner AND id=:id"),
                dict(owner=tenant, id=identifier),
            ).scalar_one()
        return int(value)

    def reserve(
        self, tenant: str, budget_id: str, reservation_id: str, request_id: str, amount_micro: int
    ) -> None:
        if type(amount_micro) is not int or not 0 <= amount_micro <= 1_000_000:
            raise ValueError("Invalid reservation")
        try:
            with self.engine.begin() as conn:
                result = conn.execute(
                    text(
                        "UPDATE sandbox_budgets SET held_micro=held_micro+:amount WHERE owner=:owner AND id=:id AND held_micro+:amount<=cap_micro"
                    ),
                    dict(owner=tenant, id=budget_id, amount=amount_micro),
                )
                if result.rowcount != 1:
                    raise DomainError(
                        ErrorCode.UNSUPPORTED, "Sandbox budget exhausted or unapproved", 429
                    )
                conn.execute(
                    text(
                        "INSERT INTO sandbox_reservations(owner,id,budget_id,request_id,reserved_micro,state) VALUES(:owner,:id,:budget,:request,:amount,'reserved')"
                    ),
                    dict(
                        owner=tenant,
                        id=reservation_id,
                        budget=budget_id,
                        request=request_id,
                        amount=amount_micro,
                    ),
                )
        except IntegrityError:
            raise DomainError(
                ErrorCode.CONFLICT, "Request already reserved; never redispatch blindly", 409
            ) from None

    def reconcile(self, tenant: str, reservation_id: str, actual_micro: int | None) -> None:
        if actual_micro is not None and (type(actual_micro) is not int or actual_micro < 0):
            raise ValueError("Invalid actual usage")
        # Retain conservative holds even for settled calls; never invent refunds.
        with self.engine.begin() as conn:
            row = (
                conn.execute(
                    text("SELECT * FROM sandbox_reservations WHERE owner=:owner AND id=:id"),
                    dict(owner=tenant, id=reservation_id),
                )
                .mappings()
                .first()
            )
            if row is None:
                raise DomainError(ErrorCode.NOT_FOUND, "Reservation not found", 404)
            if row["state"] == "reconciled":
                if row["actual_micro"] == actual_micro:
                    return
                raise DomainError(ErrorCode.CONFLICT, "Usage already reconciled", 409)
            if actual_micro is not None and actual_micro > row["reserved_micro"]:
                # A provider overage is not silently dropped. Freeze further spending.
                conn.execute(
                    text(
                        "UPDATE sandbox_budgets SET held_micro=cap_micro WHERE owner=:owner AND id=:budget"
                    ),
                    dict(owner=tenant, budget=row["budget_id"]),
                )
                actual_micro = None
            result = conn.execute(
                text(
                    "UPDATE sandbox_reservations SET state=:state,actual_micro=:actual WHERE owner=:owner AND id=:id AND state=:prior"
                ),
                dict(
                    owner=tenant,
                    id=reservation_id,
                    state="uncertain" if actual_micro is None else "reconciled",
                    actual=actual_micro,
                    prior=row["state"],
                ),
            )
            if result.rowcount != 1:
                raise DomainError(ErrorCode.CONFLICT, "Concurrent reconciliation", 409)
