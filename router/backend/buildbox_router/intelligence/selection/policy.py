"""Compile allowlisted inactive references only after rechecking the exact snapshot."""

import hashlib
import re

from ...contracts import (
    Assignment,
    CatalogSnapshot,
    DraftPolicy,
    ErrorCode,
    Recommendation,
    Workflow,
)
from ...errors import DomainError
from .engine import DeterministicSelector


class SafeDraftCompiler:
    def __init__(
        self, catalog: CatalogSnapshot, selector: DeterministicSelector | None = None
    ) -> None:
        self.catalog = CatalogSnapshot.model_validate_json(catalog.model_dump_json())
        self.selector = selector or DeterministicSelector()

    def compile(self, workflow: Workflow, recommendation: Recommendation) -> DraftPolicy:
        workflow = Workflow.model_validate_json(workflow.model_dump_json())
        recommendation = Recommendation.model_validate_json(recommendation.model_dump_json())
        if (
            recommendation.workflow_id,
            recommendation.workflow_version,
            recommendation.catalog_id,
        ) != (workflow.id, workflow.version, self.catalog.id):
            raise DomainError(
                ErrorCode.CONFLICT,
                "Workflow version or catalog snapshot mismatch; previous recommendations never automatically repin",
                409,
            )
        nodes = {n.id for n in workflow.nodes if n.kind in ("llm", "bounded_agent")}
        assignments = recommendation.assignments
        if {a.node_id for a in assignments} != nodes or len(assignments) != len(nodes):
            raise DomainError(
                ErrorCode.INVALID,
                "Incomplete, duplicate or non-model stage assignment; no draft policy produced",
            )
        current = self.selector.filter(workflow, self.catalog)
        if current != recommendation.filter_result or any(
            a.configuration_id not in current.eligible for a in assignments
        ):
            raise DomainError(
                ErrorCode.INVALID,
                "Assignment no longer admissible under exact current constraints/evidence",
            )
        if len({a.configuration_id for a in assignments}) > 3:
            raise DomainError(ErrorCode.INVALID, "Portfolio exceeds supported configuration bound")
        if recommendation.alternatives:
            raise DomainError(
                ErrorCode.UNSUPPORTED,
                "Fallback/alternative semantics cannot be compiled safely by the v1 policy contract",
            )
        identifiers = (
            workflow.id,
            recommendation.id,
            *(a.node_id for a in assignments),
            *(a.configuration_id for a in assignments),
        )
        if any(
            re.search(r"(?:sk-|ghp_|api[_-]?key|password|bearer)", value, re.IGNORECASE)
            for value in identifiers
        ):
            raise DomainError(ErrorCode.INVALID, "Credential-like identifier rejected from export")
        return DraftPolicy(
            id="policy-" + hashlib.sha256(recommendation.id.encode()).hexdigest()[:32],
            workflow_id=workflow.id,
            workflow_version=workflow.version,
            recommendation_id=recommendation.id,
            assignments=tuple(
                Assignment(
                    node_id=a.node_id,
                    configuration_id=a.configuration_id,
                    reason="Provisional mapping; evaluate and obtain human approval before any use",
                )
                for a in assignments
            ),
            synthetic=self.catalog.synthetic,
        )
