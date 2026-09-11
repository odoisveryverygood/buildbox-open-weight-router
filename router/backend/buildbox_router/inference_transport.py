"""Central approved-target transport: pinned DNS/TLS, no redirects, bounded IO.

Independent from public-source allowlists: only operator ApprovedEndpoint records
authorize target inference. Local exceptions are literal loopback IP targets.
"""

import asyncio
import http.client
import ipaddress
import socket
import ssl
import threading
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from urllib.parse import urlsplit

from .execution_contracts import ApprovedEndpoint
from .provider_contracts import ProviderRequest


def endpoint_address(endpoint: ApprovedEndpoint) -> tuple[str, int, str]:
    url = urlsplit(endpoint.url)
    host = url.hostname or ""
    if (
        url.username
        or url.password
        or url.query
        or url.fragment
        or url.path not in ("/v1/chat/completions", "/api/v1/chat/completions")
    ):
        raise ValueError("Approved endpoint path/authority rejected")
    if endpoint.expires_at <= datetime.now(UTC):
        raise ValueError("Endpoint approval expired")
    if endpoint.network == "loopback":
        if host not in ("127.0.0.1", "::1") or url.scheme != "http" or url.port is None:
            raise ValueError("Local exception requires literal loopback and exact port")
    elif url.scheme != "https" or (url.port is not None and url.port != 443):
        raise ValueError("Public inference requires HTTPS 443")
    if endpoint.adapter_id == "openrouter" and (
        host != "openrouter.ai"
        or url.path != "/api/v1/chat/completions"
        or endpoint.network != "public_https"
    ):
        raise ValueError("OpenRouter destination mismatch")
    return host, url.port or 443, url.path


async def exchange(
    endpoint: ApprovedEndpoint,
    request: ProviderRequest,
    secret: str | None,
    check: Callable[[], None],
    timeout_seconds: float,
) -> AsyncIterator[bytes]:
    host, port, path = endpoint_address(endpoint)

    class PinnedConnection(http.client.HTTPConnection):
        def connect(self) -> None:
            raise OSError("Automatic reconnect is forbidden")

    connection = PinnedConnection(host, port, timeout=min(10, timeout_seconds))
    stopped = threading.Event()

    def checked() -> None:
        if stopped.is_set():
            raise TimeoutError("Transport cancelled")
        check()

    def open_response() -> http.client.HTTPResponse:
        checked()
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not addresses or any(
            not (
                ipaddress.ip_address(a[4][0]).is_global
                if endpoint.network == "public_https"
                else ipaddress.ip_address(a[4][0]).is_loopback
            )
            for a in addresses
        ):
            raise ValueError("Resolved destination rejected")
        family, kind, protocol, _, address = addresses[0]
        sock = socket.socket(family, kind, protocol)
        connection.sock = sock  # Cleanup owns socket even if connect/TLS fails.
        sock.settimeout(min(10, timeout_seconds))
        sock.connect(address)
        if endpoint.network == "public_https":
            connection.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        checked()
        headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "identity",
            "Accept": "text/event-stream" if request.stream else "application/json",
        }
        if secret:
            headers["Authorization"] = "Bearer " + secret
        connection.request(
            "POST", path, request.model_dump_json(exclude_none=True).encode(), headers
        )
        response = connection.getresponse()
        if (
            response.status != 200
            or response.getheader("Content-Encoding", "identity") != "identity"
        ):
            raise ValueError("Upstream non-success/redirect/compression rejected")
        expected = "text/event-stream" if request.stream else "application/json"
        if response.getheader("Content-Type", "").split(";", 1)[0].strip() != expected:
            raise ValueError("Upstream content type mismatch")
        return response

    total = 0
    try:
        async with asyncio.timeout(timeout_seconds):
            response = await asyncio.to_thread(open_response)
            while True:
                checked()
                block = await asyncio.to_thread(response.read1, 8192)
                if not block:
                    break
                total += len(block)
                if total > 1048576:
                    raise ValueError("Upstream response bound exceeded")
                yield block
    finally:
        stopped.set()
        connection.close()
