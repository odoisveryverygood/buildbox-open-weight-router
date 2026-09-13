"""One foreground, loopback-only demo supervisor. Never kills another process."""

import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    api_port = int(os.getenv("BUILDBOX_DEMO_API_PORT", "8032"))
    web_port = int(os.getenv("BUILDBOX_DEMO_WEB_PORT", "5202"))
    if api_port == web_port or any(not 1024 <= p <= 65535 for p in (api_port, web_port)):
        raise SystemExit("Use two distinct unprivileged local ports")
    for port in (api_port, web_port):
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                raise SystemExit(
                    f"Port {port} is occupied. Stop your previous demo or select other BUILDBOX_DEMO_*_PORT values; no process was killed."
                ) from None
    # Inherit only process/runtime basics, never provider or production credentials.
    env = {k: os.environ[k] for k in ("PATH", "HOME", "USER", "TMPDIR", "LANG") if k in os.environ}
    env.update(
        ROUTER_ACCEPTANCE_SETUP="stakeholder",
        ROUTER_WEB_ORIGIN=f"http://127.0.0.1:{web_port}",
        ROUTER_API_ORIGIN=f"http://127.0.0.1:{api_port}",
        ROUTER_WEB_PORT=str(web_port),
    )
    if not (root / "node_modules/.bin/vite").exists():
        subprocess.run(["npm", "ci", "--ignore-scripts"], env=env, check=True)
    # Stable built UI: no development hot reload during a stakeholder presentation.
    subprocess.run(["npm", "run", "build"], env=env, check=True)
    directory = Path(tempfile.mkdtemp(prefix="buildbox-stakeholder-logs-"))
    children = []
    files = []

    def stop(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        for name, command in (
            (
                "api",
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "tests.gateway.browser_fixture:create_fixture_app",
                    "--factory",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                    "--no-access-log",
                ],
            ),
            ("web", ["npm", "exec", "--workspace", "web", "--", "vite", "preview"]),
        ):
            log = (directory / (name + ".log")).open("w")
            files.append(log)
            children.append(
                subprocess.Popen(command, env=env, stdout=log, stderr=log, start_new_session=True)
            )
        for _ in range(100):
            if any(p.poll() is not None for p in children):
                raise RuntimeError(f"Demo service exited; inspect {directory}")
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/studio/runtime", timeout=1)
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    try:
                        urllib.request.urlopen(f"http://127.0.0.1:{web_port}/", timeout=1)
                        break
                    except (OSError, urllib.error.URLError):
                        pass
            except (OSError, urllib.error.URLError):
                pass
            time.sleep(0.2)
        else:
            raise RuntimeError(f"Startup deadline exceeded; inspect {directory}")
        print(
            f"\nBuildbox stakeholder demo: http://127.0.0.1:{web_port}/?demo=1\n"
            "Local TEST identity: fixture / synthetic-test-password\n"
            "Real router, simulated upstream. No paid credentials or external calls.\n"
            "Fresh isolated database per start; previous audit data is not deleted.\n"
            f"Logs: {directory}\nCtrl-C stops only these services. Rerun make demo for a clean reset.\n",
            flush=True,
        )
        while all(p.poll() is None for p in children):
            time.sleep(0.5)
        raise RuntimeError(f"A demo service exited; inspect {directory}")
    except KeyboardInterrupt:
        print("\nStopping owned demo services; prior data retained.", flush=True)
    finally:
        for child in children:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        for log in files:
            log.close()


if __name__ == "__main__":
    main()
