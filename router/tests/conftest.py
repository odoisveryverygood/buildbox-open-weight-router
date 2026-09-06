import socket

import pytest
from buildbox_router.config import Settings
from buildbox_router.contracts import Binding, Constraints, Node, Provenance, Workflow
from buildbox_router.migrations import migrate
from buildbox_router.storage import SqlStorage, engine_for


@pytest.fixture(autouse=True)
def deny_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Ordinary tests must not connect to the network")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def provenance():
    return Provenance(kind="synthetic", source="Isolated acceptance fixture")


@pytest.fixture
def workflow(provenance):
    return Workflow(
        id="workflow-test",
        version=1,
        title="Synthetic classification",
        inputs=("text",),
        constraints=Constraints(
            max_cost_per_1k_tokens=1.0, required_region="local", provenance=provenance
        ),
        provenance=provenance,
        nodes=(
            Node(
                id="classify",
                kind="llm",
                purpose="Classify",
                inputs={"text": Binding(source="text", output="value", from_input=True)},
            ),
            Node(id="review", kind="human_approval", purpose="Review", depends_on=("classify",)),
        ),
    )


@pytest.fixture
def storage(tmp_path):
    engine = engine_for(Settings(database_url=f"sqlite:///{tmp_path}/test.db"))
    migrate(engine)
    yield SqlStorage(engine)
    engine.dispose()
