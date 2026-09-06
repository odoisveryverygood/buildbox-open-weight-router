"""One worker from the same backend package; no workflow execution engine."""

import argparse
import time

from .composition import Services, fixture_services
from .config import Settings
from .contracts import Workflow
from .storage import SqlStorage, engine_for


def run_once(services: Services) -> bool:
    claimed = services.storage.claim()
    if claimed is None:
        return False
    owner, job = claimed
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
    engine = engine_for(Settings.from_env())
    storage = SqlStorage(engine)
    storage.check_revision()
    services = fixture_services(storage)
    try:
        while True:
            run_once(services)
            if args.once:
                break
            time.sleep(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
