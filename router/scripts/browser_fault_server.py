"""Explicit test-only real API/worker with an injected provider outage, never success.

Run only against an explicitly migrated isolated DB. No application adapter flag
or production fallback is introduced. The UI/API/database remain real.
"""

import asyncio
import time
from contextlib import asynccontextmanager

import buildbox_router.planning as planning
import uvicorn
from buildbox_router.api import create_app
from buildbox_router.config import Settings
from buildbox_router.worker import run_once


def outage(check):
    check()
    time.sleep(1)
    check()
    raise TimeoutError("TEST ONLY provider outage; Bearer synthetic-do-not-echo")


if __name__ == "__main__":
    settings = Settings.from_env()
    if settings.identity_mode != "shared" or settings.mode != "fixture":
        raise RuntimeError("Browser fault server requires authenticated explicit fixture mode")
    planning.public_sources = outage
    app = create_app(settings)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):

            async def work():
                while True:
                    await asyncio.to_thread(run_once, application.state.services, settings)
                    await asyncio.sleep(0.1)

            worker = asyncio.create_task(work())
            try:
                yield
            finally:
                worker.cancel()
                await asyncio.gather(worker, return_exceptions=True)

    app.router.lifespan_context = lifespan
    uvicorn.run(app, host="127.0.0.1", port=8015, access_log=False)
