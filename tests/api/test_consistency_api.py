"""GET /api/scenarios/{id}/consistency: the consistency report in the usual envelope."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from jev.api.app import create_app
from jev.config import Settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(_env_file=None, allowed_hosts=["testserver"])  # type: ignore[call-arg]
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client


def test_reports_consistency_for_a_recorded_scenario(client: TestClient) -> None:
    body = client.get("/api/scenarios/s3_citation_check/consistency").json()

    assert body["success"] is True
    data = body["data"]
    assert len(data["recordings"]) == 3
    assert data["sides"]["jev"]["changed"] == 0
    assert data["sides"]["llm"]["changed"] == 1


def test_an_unknown_scenario_is_a_404(client: TestClient) -> None:
    response = client.get("/api/scenarios/nope/consistency")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UNKNOWN_SCENARIO"
