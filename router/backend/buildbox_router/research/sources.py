"""Public snapshot replay behind SearchPort; no HTTP client or credential lookup.

The foundation has no shared protected fetch transport. Live extraction therefore
fails closed. Reference checks below protect replay lookup only; they are NOT a
replacement for DNS/connection/redirect validation in the integration transport.
"""

import ipaddress
import json
from collections.abc import Iterable
from urllib.parse import urlsplit

from ..ports import SearchPort
from .normalizers import REPOSITORY
from .records import SourceCapture, Status, failure

SOURCE_DOMAINS = frozenset({"huggingface.co", "openrouter.ai"})


def public_reference(url: str) -> None:
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        if (
            parsed.scheme != "https"
            or host not in SOURCE_DOMAINS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.fragment
            or parsed.query
            or any(c in url for c in ("\\", "\r", "\n", "\t", "%"))
            or "/../" in parsed.path
        ):
            raise ValueError("Unapproved reference")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError("IP literals are not public source identities")
    except ValueError:
        raise failure(Status.UNSAFE, "Unapproved public source reference") from None


def discovery_query(repository: str) -> str:
    if not REPOSITORY.fullmatch(repository):
        raise failure(Status.UNSAFE, "Discovery accepts an exact public repository ID only")
    return f"publisher repository {repository}"


class RecordedSources:
    """An independently runnable offline SearchPort adapter, never a live connector."""

    def __init__(self, captures: Iterable[SourceCapture]) -> None:
        sources: dict[str, str] = {}
        queries: dict[str, tuple[str, ...]] = {}
        for capture in captures:
            if len(sources) >= 64:
                raise failure(Status.SEARCH_LIMIT, "Public replay is capped at 64 source captures")
            public_reference(capture.url)
            if capture.url in sources:
                raise failure(Status.CONFLICT, "Duplicate captured source URL")
            sources[capture.url] = capture.model_dump_json()
            prefix = "https://huggingface.co/api/models/"
            if capture.source_type == "publisher_metadata" and capture.url.startswith(prefix):
                queries[discovery_query(capture.url[len(prefix) :])] = (capture.url,)
        self._sources = sources
        self._queries = queries

    def search(self, *, query: str, limit: int) -> tuple[str, ...]:
        if limit < 1 or limit > 12:
            raise failure(Status.SEARCH_LIMIT, "Search limit must be between 1 and 12")
        if query not in self._queries:
            # Do not echo/log arbitrary queries or pass them to any external service.
            raise failure(Status.PARTIAL, "No captured results for this approved identity")
        return self._queries[query][:limit]

    def extract(self, *, url: str) -> str:
        return self.capture(url).body

    def capture(self, url: str) -> SourceCapture:
        public_reference(url)
        payload = self._sources.get(url)
        if payload is None:
            raise failure(Status.INACCESSIBLE, "Public source was not captured")
        return SourceCapture.model_validate_json(payload)

    def snapshot_key(self) -> str:
        # Contains public references and immutable body digests, never workload data.
        return json.dumps(sorted(self._sources.items()), separators=(",", ":"))

    def captures(self) -> tuple[SourceCapture, ...]:
        return tuple(SourceCapture.model_validate_json(v) for _, v in sorted(self._sources.items()))


class RuntimePublicSearch:
    """Frozen SearchPort placeholder pending the shared fetch/approval contract.

    Do not enable by flipping a flag. Integration must supply and test the guarded
    transport, independent runtime authentication, and authoritative spend limits.
    """

    def search(self, *, query: str, limit: int) -> tuple[str, ...]:
        raise failure(
            Status.UNAVAILABLE, "Runtime search needs approved shared transport and spend controls"
        )

    def extract(self, *, url: str) -> str:
        raise failure(
            Status.UNAVAILABLE, "Runtime extraction needs shared connection/redirect protections"
        )


# Structural conformance is checked by mypy without constructing any live client.
def as_search_port(sources: RecordedSources | RuntimePublicSearch) -> SearchPort:
    return sources
