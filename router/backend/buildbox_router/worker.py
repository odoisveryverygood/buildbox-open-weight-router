"""One existing worker: planning plus explicitly configured bounded runtime jobs."""

import argparse
import asyncio
import time

from .composition import Services, product_services
from .config import Settings
from .contracts import Workflow
from .execution_jobs import QueuedWorkflows
from .execution_ports import ExecutionServices
from .planning import PlanningService
from .planning_storage import PlanningStorage
from .storage import SqlStorage, engine_for


def run_once(
    services: Services,
    settings: Settings | None = None,
    *,
    execution: ExecutionServices | None = None,
) -> bool:
    if settings and settings.runtime_registry_file and isinstance(services.storage, SqlStorage):
        from .execution_composition import configured_execution
        from .execution_storage import SandboxStorage

        execution = configured_execution(
            settings, SandboxStorage(services.storage.engine), services.selector
        )
    if (
        execution
        and isinstance(execution.workflows, QueuedWorkflows)
        and asyncio.run(execution.workflows.work_once())
    ):
        return True
    claimed = services.storage.claim()
    if claimed is None:
        return False
    owner, job = claimed
    if job.operation == "planning" and isinstance(services.storage, SqlStorage):
        PlanningService(PlanningStorage(services.storage.engine), settings or Settings()).run(
            owner, job
        )
        return True
    try:
        workflow = Workflow.model_validate_json(
            services.storage.get(owner, "workflow", job.workflow_id, job.workflow_version)
        )
        catalog = services.research.research(workflow)
        recommendation = services.selector.recommend(workflow, catalog, job.id)
        services.storage.finish(owner, job, recommendation, catalog)
    except Exception:
        # Never persist exception strings: adapters may include credential-bearing URLs.
        services.storage.fail(owner, job)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env()
    engine = engine_for(settings)
    storage = PlanningStorage(engine)
    storage.check_revision()
    services = product_services(storage)
    try:
        while True:
            run_once(services, settings)
            if args.once:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
