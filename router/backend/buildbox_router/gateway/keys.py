"""Application secrets are independent random credentials, never provider keys."""

import hashlib
import hmac
import re
import secrets
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from ..contracts import ErrorCode
from ..errors import DomainError
from ..execution_contracts import ApplicationKeyMetadata, Scope, VersionRef
from ..execution_ports import RequestContext
from ..execution_security import authorize_application_key
from ..execution_storage import SandboxStorage


class ApplicationKeys:
    def __init__(self, store: SandboxStorage, *, requests_per_minute: int = 30) -> None:
        if not 1 <= requests_per_minute <= 1000:
            raise ValueError("Invalid server rate limit")
        self.store = store
        self.requests_per_minute = requests_per_minute

    def issue(
        self,
        context: RequestContext,
        *,
        expires_at: datetime,
        scopes: tuple[Scope, ...],
        aliases: tuple[str, ...] = (),
        policies: tuple[VersionRef, ...] = (),
        max_cost_micro_usd: int,
    ) -> tuple[ApplicationKeyMetadata, str]:
        # Integration must call only with its authenticated studio context.
        # App keys cannot mint other keys or expand their own authority.
        context.check_cancelled()
        if context.application_key is not None or context.principal_id != context.tenant_id:
            raise DomainError(
                ErrorCode.UNSUPPORTED, "Studio identity required for key issuance", 403
            )
        for alias in aliases:
            self.store.alias(context.tenant_id, alias)
        for policy in policies:
            self.store.policy(context.tenant_id, policy)
        identifier = uuid4().hex
        prefix = "bbx_" + secrets.token_hex(4)
        value = ApplicationKeyMetadata(
            id=identifier,
            tenant_id=context.tenant_id,
            prefix=prefix,
            scopes=scopes,
            alias_ids=aliases,
            workflow_policies=policies,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
        )
        raw = f"{prefix}.{context.tenant_id}.{identifier}.{secrets.token_hex(32)}"
        salt = secrets.token_hex(16)
        verifier = hashlib.pbkdf2_hmac("sha256", raw.encode(), salt.encode(), 310000).hex()
        self.store.provision_budget(context.tenant_id, "key-" + identifier, max_cost_micro_usd)
        self.store.save_application_key(
            context.tenant_id, value, f"pbkdf2_sha256:310000:{salt}:{verifier}"
        )
        return value, raw  # Caller reveals once; no retained raw secret.

    async def authenticate(self, bearer: str, now: datetime) -> ApplicationKeyMetadata:
        match = re.fullmatch(
            r"(bbx_[a-f0-9]{8})\.([A-Za-z0-9_-]{1,80})\.([a-f0-9]{32})\.([a-f0-9]{64})", bearer
        )
        record = None
        salt, expected, rounds = "0" * 32, "0" * 64, 310000
        if match:
            try:
                record, verifier = self.store.key_record(match[2], match[3])
                _, iteration, salt, expected = verifier.split(":")
                rounds = int(iteration)
            except DomainError:
                pass
        actual = hashlib.pbkdf2_hmac("sha256", bearer[:512].encode(), salt.encode(), rounds).hex()
        if not hmac.compare_digest(actual, expected) or record is None or not match:
            raise DomainError(ErrorCode.UNSUPPORTED, "Invalid application key", 401)
        if (
            record.prefix != match[1]
            or record.revoked_at
            or not record.created_at <= now < record.expires_at
        ):
            raise DomainError(ErrorCode.UNSUPPORTED, "Invalid application key", 401)
        return record

    def check(
        self, context: RequestContext, scope: Scope, *, alias: str | None = None
    ) -> ApplicationKeyMetadata:
        if context.application_key is None:
            raise DomainError(ErrorCode.UNSUPPORTED, "Application key required", 401)
        fresh, _ = self.store.key_record(context.tenant_id, context.application_key.id)
        authorize_application_key(context.tenant_id, fresh, scope, datetime.now(UTC), alias=alias)
        return fresh

    def reserve(self, context: RequestContext, amount: int, scope: Scope = "chat:complete") -> None:
        key = self.check(context, scope)
        minute = int(datetime.now(UTC).timestamp()) // 60
        window = f"rate-{key.id}-{minute}"
        try:
            self.store.provision_budget(context.tenant_id, window, self.requests_per_minute)
        except IntegrityError:
            pass  # Existing immutable window cap; reserve below is atomic.
        self.store.reserve(
            context.tenant_id, window, "rate-" + context.request_id, "rate-" + context.request_id, 1
        )
        self.store.reserve(
            context.tenant_id,
            "key-" + key.id,
            "key-" + context.request_id,
            "key-" + context.request_id,
            amount,
        )

    async def revoke(self, context: RequestContext, key_id: str) -> ApplicationKeyMetadata:
        context.check_cancelled()
        if context.application_key is not None or context.principal_id != context.tenant_id:
            raise DomainError(ErrorCode.UNSUPPORTED, "Studio identity required to revoke keys", 403)
        return self.store.revoke_key(context.tenant_id, key_id, datetime.now(UTC))
