"""Immutable revision helpers; never repin previous jobs or recommendations."""

from ...contracts import ErrorCode, Intake, Interpretation, Workflow
from ...errors import DomainError
from ...ports import Interpreter, StoragePort


def revise_workflow(
    previous: Workflow, revised_intake: Intake, interpreter: Interpreter
) -> Interpretation:
    result = interpreter.interpret(revised_intake, previous.id)
    if result.workflow is None:
        return result
    payload = result.workflow.model_dump(mode="json")
    payload.update(id=previous.id, version=previous.version + 1)
    return Interpretation(status="ready", workflow=Workflow.model_validate(payload))


def persist_revision(
    storage: StoragePort, owner: str, previous: Workflow, revision: Workflow
) -> None:
    saved = Workflow.model_validate_json(
        storage.get(owner, "workflow", previous.id, previous.version)
    )
    if saved != previous or revision.id != previous.id or revision.version != previous.version + 1:
        raise DomainError(
            ErrorCode.CONFLICT, "Revision must follow the exact owned immutable version", 409
        )
    revision = Workflow.model_validate_json(revision.model_dump_json())
    storage.put(owner, "workflow", revision.id, revision.model_dump_json(), revision.version)
