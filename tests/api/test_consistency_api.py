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


def test_a_scenario_without_recordings_is_a_404(tmp_path: object) -> None:
    from pathlib import Path

    from jev.replay.store import FileReplayStore
    from jev.runs.service import RunService
    from jev.scenarios.registry import get_scenario
    from tests.s1.facts import DATA

    settings = Settings(_env_file=None, allowed_hosts=["testserver"])  # type: ignore[call-arg]
    spec = get_scenario("s3")
    assert spec is not None
    store = FileReplayStore(Path(str(tmp_path)))
    service = RunService(settings, scenario=spec, data_dir=DATA, store=store)
    with TestClient(create_app(settings=settings, service=service)) as client:
        response = client.get(f"/api/scenarios/{spec.id}/consistency")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NO_RECORDING"
