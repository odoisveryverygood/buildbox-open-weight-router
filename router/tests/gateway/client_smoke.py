"""Opt-in local HTTP acceptance D. Synthetic upstream; zero vendor requests.

uv run python -m tests.gateway.client_smoke
Subprocess clients receive an ephemeral APPLICATION key via their environment.
No key value is printed or passed as a command-line argument.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time

import uvicorn

from .browser_fixture import create_fixture_app
from .test_unblock import sse, wire


def main():
    app = create_fixture_app()
    fixture, state = app.state.synthetic_context

    def respond(body):
        state.parts = None
        state.result = wire(content="SIMULATED support: shipping takes 3 days.")
        if body.get("stream"):
            state.parts = [
                sse({"content": "SIMULATED streamed support"}),
                sse({}, "stop"),
                sse(
                    usage={
                        "prompt_tokens": 10,
                        "completion_tokens": 2,
                        "total_tokens": 12,
                        "cost": 0,
                    }
                ),
                b"data: [DONE]\n\n",
            ]
        elif body.get("tools") and body["messages"][-1]["role"] != "tool":
            state.result = wire(
                content=None,
                calls=[
                    {
                        "id": "call-support-9",
                        "type": "function",
                        "function": {"name": "lookup_support", "arguments": '{"key":"shipping"}'},
                    }
                ],
            )

    state.respond = respond
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error", access_log=False)
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    assert server.started
    env = dict(
        os.environ,
        BUILDBOX_API_BASE=f"http://127.0.0.1:{sock.getsockname()[1]}",
        BUILDBOX_API_KEY=fixture.raw,
    )
    count = 0
    try:
        for command in (
            [sys.executable, "examples/chat.py"],
            ["node", "--experimental-strip-types", "examples/chat.ts"],
        ):
            for args in (
                ["--list"],
                ["--alias", "test-alias"],
                ["--alias", "test-alias", "--stream"],
                ["--alias", "test-alias", "--tool-roundtrip"],
            ):
                done = subprocess.run(
                    [*command, *args], env=env, capture_output=True, text=True, timeout=45
                )
                assert done.returncode == 0, (
                    f"Client failed: {command[0]} {args}; details retained in memory only"
                )
                assert fixture.raw not in done.stdout + done.stderr
                assert (
                    "[DONE]" in done.stdout if "--stream" in args else "test-alias" in done.stdout
                )
                count += 1
        # cURL credentials travel on stdin config, never argv or console.
        config = f'url = "{env["BUILDBOX_API_BASE"]}/v1/models"\nheader = "Authorization: Bearer {fixture.raw}"\nsilent\nshow-error\nfail\n'
        done = subprocess.run(
            ["curl", "--config", "-"], input=config, capture_output=True, text=True, timeout=30
        )
        assert done.returncode == 0 and "test-alias" in done.stdout
        count += 1
        tool_results = [
            body["messages"][-1] for body in state.seen if body["messages"][-1]["role"] == "tool"
        ]
        assert len(tool_results) == 2 and all(
            m["tool_call_id"] == "call-support-9" for m in tool_results
        )
        attempts = fixture.store.records("alice", "attempt")
        assert len(attempts) == 8
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "client_checks": count,
                    "python": 4,
                    "typescript": 4,
                    "curl": 1,
                    "attempts": len(attempts),
                    "tool_id_roundtrips": len(tool_results),
                    "live_provider": False,
                    "external_requests": 0,
                }
            )
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
