"""The API serves every registered scenario by id, each with its own documents and recordings."""

from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jev.api.app import create_app
from jev.config import Settings
from jev.replay.store import FileReplayStore
from jev.runs.service import RunService
from jev.scenarios.registry import get_scenario
from jev.scenarios.s1_reconciliation.documents import SCENARIO_ID
from tests.s1.facts import DATA

COPY_ID = "s1_copy"


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(_env_file=None, allowed_hosts=["testserver"])  # type: ignore[call-arg]
    s1 = get_scenario(SCENARIO_ID)
    assert s1 is not None
    copy = replace(s1, id=COPY_ID, title="A second scenario", description="Same data, new id.")
    services = {
        spec.id: RunService(
            settings, scenario=spec, data_dir=DATA, store=FileReplayStore(DATA / "replays")
        )
        for spec in (s1, copy)
    }
    with TestClient(create_app(settings=settings, services=services)) as test_client:
        yield test_client


def test_lists_every_registered_scenario_in_order(client: TestClient) -> None:
    listing = client.get("/api/scenarios").json()["data"]

    assert [s["id"] for s in listing] == [SCENARIO_ID, COPY_ID]
    assert listing[1]["title"] == "A second scenario"


def test_detail_and_documents_resolve_by_id(client: TestClient) -> None:
    detail = client.get(f"/api/scenarios/{COPY_ID}").json()["data"]
    docs = client.get(f"/api/scenarios/{COPY_ID}/documents").json()["data"]

    assert detail["id"] == COPY_ID
    assert detail["description"] == "Same data, new id."
    assert docs[0]["doc_id"] == "msa"


def test_recordings_are_looked_up_under_the_scenarios_own_id(client: TestClient) -> None:
    s1_recordings = client.get(f"/api/scenarios/{SCENARIO_ID}/recordings").json()["data"]
    copy_recordings = client.get(f"/api/scenarios/{COPY_ID}/recordings").json()["data"]

    assert len(s1_recordings) > 0
    assert copy_recordings == []


def test_a_replay_of_a_scenario_without_recordings_is_refused(client: TestClient) -> None:
    response = client.post("/api/runs", json={"scenario_id": COPY_ID, "mode": "replay"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NO_RECORDING"


@pytest.mark.parametrize(
    "path",
    ["/api/scenarios/nope", "/api/scenarios/nope/documents", "/api/scenarios/nope/recordings"],
)
def test_unknown_scenario_is_a_404(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UNKNOWN_SCENARIO"


def test_one_live_run_at_a_time_holds_across_scenarios(client: TestClient) -> None:
    state = client.app.state  # type: ignore[attr-defined]
    state.settings = state.settings.model_copy(update={"live_enabled": True})
    assert state.runs.try_claim_live()  # as if a live S1 run were in progress

    response = client.post("/api/runs", json={"scenario_id": COPY_ID, "mode": "live"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RUN_IN_PROGRESS"


def test_a_single_service_is_keyed_by_its_scenario_id() -> None:
    settings = Settings(_env_file=None, allowed_hosts=["testserver"])  # type: ignore[call-arg]
    app = create_app(settings=settings, service=RunService(settings, data_dir=DATA))

    assert list(app.state.services) == [SCENARIO_ID]


def test_conflicting_or_mislabelled_services_are_refused() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    s1 = RunService(settings, data_dir=DATA)

    with pytest.raises(ValueError, match="not both"):
        create_app(settings=settings, service=s1, services={SCENARIO_ID: s1})
    with pytest.raises(ValueError, match="runs 's1_reconciliation'"):
        create_app(settings=settings, services={"other": s1})


def test_starting_a_run_for_an_unknown_scenario_is_a_404(client: TestClient) -> None:
    response = client.post("/api/runs", json={"scenario_id": "nope", "mode": "replay"})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "UNKNOWN_SCENARIO"
