"""Explicit local browser test composition; never a production entry point.

uv run uvicorn tests.gateway.browser_fixture:create_fixture_app --factory --host 127.0.0.1 --port 8029
Fresh temporary DB, known synthetic Basic identity, HTTP fixture provider only.
"""

import json
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from buildbox_router.api import create_app
from buildbox_router.auth import password_hash
from buildbox_router.composition import fixture_services
from buildbox_router.config import Settings
from buildbox_router.execution_composition import compose_execution
from buildbox_router.migrations import migrate
from buildbox_router.planning_storage import PlanningStorage
from buildbox_router.storage import engine_for
from buildbox_router.worker import run_once

from .conftest import rt
from .test_unblock import loopback


def create_fixture_app():
    directory = Path(tempfile.mkdtemp(prefix="buildbox-7b-browser-"))
    auth = directory / "synthetic-auth.json"
    auth.write_text(
        json.dumps(
            [
                {
                    "username": "fixture",
                    "owner": "alice",
                    "salt": "0" * 32,
                    "password_hash": password_hash("synthetic-test-password", "0" * 32),
                }
            ]
        )
    )
    settings = Settings(
        database_url=f"sqlite:///{directory}/fixture.db",
        identity_mode="shared",
        auth_file=str(auth),
        web_origin="http://127.0.0.1:5199",
    )
    engine = engine_for(settings)
    migrate(engine)
    storage = PlanningStorage(engine)
    with ThreadPoolExecutor(max_workers=1) as executor:
        fixture = executor.submit(rt.__wrapped__, storage).result()
    patch = pytest.MonkeyPatch()
    upstream = loopback.__wrapped__(fixture, patch)
    state = next(upstream)
    services = fixture_services(storage)
    execution = compose_execution(
        fixture.store, state.registry, services.selector, retention_seconds=3600
    )
    app = create_app(settings, services, execution, fixture.store)
    app.state.synthetic_upstream = (upstream, patch)

    def work():
        while True:
            run_once(services, execution=execution)
            time.sleep(0.1)

    threading.Thread(target=work, daemon=True).start()
    return app
