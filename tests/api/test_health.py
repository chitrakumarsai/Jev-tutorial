from fastapi.testclient import TestClient

from jev.api.app import create_app


def test_health_returns_ok_envelope() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"status": "ok"}, "error": None}
