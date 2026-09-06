import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    mode: Literal["fixture", "live"] = "fixture"
    identity_mode: Literal["local_fixture", "shared"] = "local_fixture"
    database_url: str = Field(default="sqlite:///.local/router.db", repr=False)
    fixture_owner: Literal["local-fixture-user"] = "local-fixture-user"
    auth_file: str | None = Field(default=None, repr=False)
    approvals_file: str | None = Field(default=None, repr=False)
    local_interpretation_model: str | None = Field(
        default=None, pattern=r"^[a-zA-Z0-9_.-]+:[a-zA-Z0-9_.-]+$"
    )
    web_origin: str = Field(
        default="http://127.0.0.1:5173", pattern=r"^http://(?:127\.0\.0\.1|localhost):[0-9]{2,5}$"
    )

    @model_validator(mode="after")
    def safe_configuration(self) -> "Settings":
        if self.identity_mode == "shared" and not self.auth_file:
            raise ValueError(
                "Shared mode requires a real verified authentication adapter; none is installed"
            )
        if self.mode != "fixture" and self.identity_mode != "shared":
            raise ValueError("Live adapters are not enabled in this milestone; no fixture fallback")
        try:
            url = make_url(self.database_url)
        except ArgumentError:
            raise ValueError("Invalid database configuration") from None
        if url.drivername not in ("sqlite", "postgresql+psycopg"):
            raise ValueError("Use SQLite fixture storage or PostgreSQL with psycopg")
        if url.drivername == "sqlite" and (not url.database or url.database == ":memory:"):
            raise ValueError("Use a durable file, not an in-memory application database")
        if url.drivername != "sqlite" and url.host not in ("127.0.0.1", "localhost"):
            raise ValueError("Offline foundation permits only a local PostgreSQL host")
        return self

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.model_validate(
            {
                "mode": os.getenv("ROUTER_MODE", "fixture"),
                "identity_mode": os.getenv("ROUTER_IDENTITY_MODE", "local_fixture"),
                "database_url": os.getenv("ROUTER_DATABASE_URL", "sqlite:///.local/router.db"),
                "auth_file": os.getenv("ROUTER_AUTH_FILE"),
                "approvals_file": os.getenv("ROUTER_APPROVALS_FILE"),
                "local_interpretation_model": os.getenv("ROUTER_LOCAL_INTERPRETATION_MODEL"),
                "web_origin": os.getenv("ROUTER_WEB_ORIGIN", "http://127.0.0.1:5173"),
            }
        )

    def prepare_local_directory(self) -> None:
        url = make_url(self.database_url)
        if url.drivername == "sqlite" and url.database:
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
