import ast
from pathlib import Path


def test_lanes_do_not_import_each_other():
    root = Path("backend/buildbox_router")
    for lane, forbidden in (("intelligence", "research"), ("research", "intelligence")):
        for path in (root / lane).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.ImportFrom):
                    assert forbidden not in (node.module or "").split(".")
                elif isinstance(node, ast.Import):
                    assert all(forbidden not in alias.name.split(".") for alias in node.names)


def test_imports_do_not_create_network_clients():
    import pytest
    from buildbox_router.adapters import OfflineInference, OfflineSearch
    from buildbox_router.errors import DomainError

    with pytest.raises(DomainError):
        OfflineInference().complete(role="interpreter", prompt="Synthetic")
    with pytest.raises(DomainError):
        OfflineSearch().search(query="Synthetic", limit=1)
