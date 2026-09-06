import pytest
from buildbox_router.api import create_app
from buildbox_router.composition import example, fixture_services
from buildbox_router.config import Settings
from buildbox_router.worker import run_once
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_complete_api_fixture_flow(storage):
    services = fixture_services(storage)
    with TestClient(create_app(services=services)) as client:
        selected = client.get("/api/examples").json()[0]
        result = client.post("/api/intakes", json=selected["intake"])
        assert result.status_code == 201
        submitted = result.json()
        job_id = submitted["job"]["id"]
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "queued"
        assert run_once(services)
        assert client.get(f"/api/jobs/{job_id}").json()["status"] == "succeeded"
        rec = client.get(f"/api/recommendations/{job_id}").json()
        assert rec["confidence"] == "synthetic_only"
        assert client.get(f"/api/recommendations/{job_id}/evidence").json()["synthetic"]
        policy = client.post(f"/api/recommendations/{job_id}/policy").json()
        assert policy["active"] is False and policy["status"] == "draft"
        assert client.post(f"/api/recommendations/{job_id}/policy").json() == policy
        evaluation = client.post(f"/api/recommendations/{job_id}/evaluation").json()
        assert evaluation["status"] == "not_run" and evaluation["metric"]["value"] is None
        assert client.get(f"/api/intakes/{submitted['intake_id']}").status_code == 200
        workflow = submitted["interpretation"]["workflow"]
        workflow["version"] = 2
        path = f"/api/workflows/{workflow['id']}/versions"
        assert client.post(path, json=workflow).status_code == 201
        assert client.post(path, json=workflow).status_code == 409


def test_free_text_does_not_silently_use_fixture(storage):
    with TestClient(create_app(services=fixture_services(storage))) as client:
        intake = example().intake.model_dump(mode="json")
        intake["description"] = "Buy something online"
        result = client.post("/api/intakes", json=intake).json()
        assert result["interpretation"]["status"] == "needs_clarification" and result["job"] is None


def test_api_privacy_and_origin_boundary(storage):
    with TestClient(create_app(services=fixture_services(storage))) as client:
        result = client.post("/api/intakes", json={"secret": "do-not-echo"})
        assert result.status_code == 422 and "do-not-echo" not in result.text
        assert client.get("/api/jobs/unknown").status_code == 404
        assert (
            client.get("/api/examples", headers={"Origin": "https://untrusted.invalid"}).status_code
            == 403
        )
        assert client.get("/api/examples", headers={"Host": "untrusted.invalid"}).status_code == 400


@pytest.mark.parametrize(
    "settings",
    [
        {"mode": "live"},
        {"identity_mode": "shared"},
        {"database_url": "sqlite:///:memory:"},
        {"database_url": "postgresql+psycopg://remote.invalid/db"},
    ],
)
def test_configuration_fails_closed(settings):
    with pytest.raises((ValueError, ValidationError)):
        Settings(**settings)


def test_configuration_errors_do_not_echo_connection_secrets():
    with pytest.raises(ValueError) as exc:
        Settings(
            mode="live",
            database_url="postgresql+psycopg://user:synthetic-private-marker@localhost/db",
        )
    assert "synthetic-private-marker" not in str(exc.value)
