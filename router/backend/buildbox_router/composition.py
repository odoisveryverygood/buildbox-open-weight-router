from dataclasses import dataclass, replace

from .adapters import OfflineInference, OfflineSearch
from .contracts import Constraints, Example, Intake, Provenance
from .intelligence.fixture import (
    FixtureInterpreter,
    FixtureSelector,
    NoWriteEvaluator,
    SafePolicyCompiler,
)
from .ports import (
    CatalogPort,
    Evaluator,
    InferencePort,
    Interpreter,
    PolicyCompiler,
    ResearchPort,
    SearchPort,
    Selector,
    StoragePort,
)
from .research.fixture import SyntheticCatalog


def example() -> Example:
    return Example(
        id="document-triage",
        title="Document triage",
        intake=Intake(
            example_id="document-triage",
            description="Normalize a synthetic document, classify it, then ask a human to review. Do not send or change anything.",
            constraints=Constraints(
                max_cost_per_1k_tokens=1.0,
                required_region="local",
                provenance=Provenance(kind="synthetic", source="Example-only constraints"),
            ),
        ),
    )


@dataclass(frozen=True)
class Services:
    storage: StoragePort
    interpreter: Interpreter
    selector: Selector
    catalog: CatalogPort
    research: ResearchPort
    evaluator: Evaluator
    compiler: PolicyCompiler
    inference: InferencePort
    search: SearchPort


def fixture_services(storage: StoragePort) -> Services:
    catalog = SyntheticCatalog()
    return Services(
        storage,
        FixtureInterpreter(example()),
        FixtureSelector(),
        catalog,
        catalog,
        NoWriteEvaluator(),
        SafePolicyCompiler(),
        OfflineInference(),
        OfflineSearch(),
    )


def product_services(storage: StoragePort) -> Services:
    """One evidence-gated selector for planning, draft validation and all runtime calls.

    Legacy example ports remain offline; they cannot supply runtime credentials.
    Planning interpretation uses its separately authorized adapter in planning.py.
    """
    from .intelligence.selection.engine import DeterministicSelector

    return replace(fixture_services(storage), selector=DeterministicSelector())
