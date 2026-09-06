"""Frozen lane boundary: depend on contracts/ports, never the sibling lane."""

from typing import Protocol

from .contracts import (
    CatalogSnapshot,
    Clarification,
    DraftPolicy,
    EvaluationRun,
    FilterResult,
    Intake,
    Interpretation,
    Job,
    Recommendation,
    StackComparison,
    Workflow,
)


class InferencePort(Protocol):
    def complete(self, *, role: str, prompt: str) -> str: ...


class SearchPort(Protocol):
    def search(self, *, query: str, limit: int) -> tuple[str, ...]: ...
    def extract(self, *, url: str) -> str: ...


class Interpreter(Protocol):
    def interpret(self, intake: Intake, workflow_id: str) -> Interpretation: ...


class Clarifier(Protocol):
    def clarify(self, intake: Intake) -> tuple[Clarification, ...]: ...


class CatalogPort(Protocol):
    def snapshot(self) -> CatalogSnapshot: ...


class ResearchPort(Protocol):
    def research(self, workflow: Workflow) -> CatalogSnapshot: ...


class Selector(Protocol):
    def filter(self, workflow: Workflow, catalog: CatalogSnapshot) -> FilterResult: ...
    def rank(
        self, workflow: Workflow, catalog: CatalogSnapshot, result: FilterResult
    ) -> tuple[str, ...]: ...
    def compare(self, catalog: CatalogSnapshot, ranked: tuple[str, ...]) -> StackComparison: ...
    def recommend(
        self, workflow: Workflow, catalog: CatalogSnapshot, recommendation_id: str
    ) -> Recommendation: ...


class Evaluator(Protocol):
    def evaluate(self, recommendation: Recommendation, holdout_ref: str) -> EvaluationRun: ...


class PolicyCompiler(Protocol):
    def compile(self, workflow: Workflow, recommendation: Recommendation) -> DraftPolicy: ...


class StoragePort(Protocol):
    def put(
        self, owner: str, kind: str, object_id: str, payload: str, version: int = 1
    ) -> None: ...
    def get(self, owner: str, kind: str, object_id: str, version: int = 1) -> str: ...
    def enqueue(self, owner: str, job: Job) -> None: ...
    def job(self, owner: str, job_id: str) -> Job: ...
    def claim(self) -> tuple[str, Job] | None: ...
    def finish(
        self, owner: str, job: Job, recommendation: Recommendation, catalog: CatalogSnapshot
    ) -> None: ...
    def fail(self, owner: str, job: Job) -> None: ...
