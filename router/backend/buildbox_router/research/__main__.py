"""Explicit offline public snapshot replay; never a live search or inference CLI."""

import argparse
import json
from pathlib import Path

from ..config import Settings
from ..migrations import migrate
from ..storage import SqlStorage, engine_for
from .jobs import ResearchPlan
from .records import SourceCapture
from .service import PublicResearch
from .sources import RecordedSources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    captures = tuple(SourceCapture.model_validate(x) for x in json.loads(args.sources.read_text()))
    plan = ResearchPlan.model_validate_json(args.plan.read_text())
    engine = engine_for(Settings(database_url=f"sqlite:///{args.database.resolve()}"))
    try:
        migrate(engine)
        service = PublicResearch(
            sources=RecordedSources(captures), plan=plan, storage=SqlStorage(engine)
        )
        catalog = service.run()
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "catalog.json").write_text(
            catalog.snapshot().model_dump_json(indent=2) + "\n"
        )
        (args.output / "ledger.json").write_text(catalog.ledger().model_dump_json(indent=2) + "\n")
        print(
            json.dumps(
                {
                    "mode": "offline_public_replay",
                    "catalog_id": catalog.snapshot_id,
                    "artifacts": len(catalog.ledger().artifacts),
                    "endpoint_declarations": len(catalog.ledger().endpoints),
                    "bound_configurations": len(catalog.snapshot().configurations),
                    "claims": len(catalog.ledger().claims),
                    "retained_sources": len(catalog.ledger().sources),
                    "statuses": sorted({i.status.value for i in catalog.ledger().issues}),
                    "model_quality_validated": False,
                    "runtime_network_available": False,
                },
                indent=2,
            )
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
