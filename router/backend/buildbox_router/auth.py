"""Explicit operator-provisioned identities. Passwords never enter saved plans or logs.

Basic authentication is suitable only on loopback or behind TLS. This application
does not authorize shared/public deployment or provision credentials automatically.
"""

import base64
import hashlib
import hmac
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .contracts import Identifier


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    username: Identifier
    owner: Identifier
    salt: str = Field(min_length=32, max_length=64)
    password_hash: str = Field(pattern=r"^[a-f0-9]{64}$", repr=False)


def password_hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 310_000).hex()


class Authenticator:
    def __init__(self, path: str) -> None:
        data = json.loads(Path(path).read_text())
        self.identities = tuple(Identity.model_validate(x) for x in data)
        if not self.identities or len({x.username for x in self.identities}) != len(
            self.identities
        ):
            raise ValueError("Authentication configuration requires unique identities")

    def owner(self, authorization: str) -> str | None:
        try:
            scheme, token = authorization.split(" ", 1)
            if scheme.lower() != "basic" or len(token) > 2048:
                return None
            username, password = base64.b64decode(token, validate=True).decode().split(":", 1)
        except (ValueError, UnicodeError):
            return None
        identity = next((x for x in self.identities if x.username == username), None)
        salt = identity.salt if identity else "0" * 32
        digest = password_hash(password, salt)
        return (
            identity.owner
            if identity and hmac.compare_digest(digest, identity.password_hash)
            else None
        )
