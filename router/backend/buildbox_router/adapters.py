"""Integration-owned transports. No credential-dependent imports or live fallback."""

from .contracts import ErrorCode
from .errors import DomainError


class OfflineInference:
    def complete(self, *, role: str, prompt: str) -> str:
        raise DomainError(ErrorCode.UNSUPPORTED, "Inference disabled in offline foundation")


class OfflineSearch:
    def search(self, *, query: str, limit: int) -> tuple[str, ...]:
        raise DomainError(ErrorCode.UNSUPPORTED, "Live search disabled in offline foundation")

    def extract(self, *, url: str) -> str:
        raise DomainError(ErrorCode.UNSUPPORTED, "Live extraction disabled in offline foundation")
