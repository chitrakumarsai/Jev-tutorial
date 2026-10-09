"""HTTP API: scenarios, runs (live + replay), SSE events, budget. Envelope everywhere."""

import json
import time
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from jev.api.app import create_app
from jev.budget.guard import BudgetGuard
from jev.budget.ledger import Ledger
from jev.config import Settings
from jev.replay.store import FileReplayStore
from jev.runs.service import RunService
from tests.helpers import initialised_ledger
from tests.runs.test_service import FakeLiveClients, FakeLiveLlm
from tests.s1.facts import DATA

_OPEN: list[TestClient] = []


@pytest.fixture(autouse=True)
def _close_clients() -> Iterator[None]:
    """Clients stay open for the whole test so background runs share one event loop."""
    yield
    while _OPEN:
        _OPEN.pop().__exit__(None, None, None)


def make_client(
    tmp_path: Path, *, live: bool = True, clients: FakeLiveClients | None = None
) -> TestClient:
    ledger = tmp_path / "ledger.jsonl"
    initialised_ledger(ledger)
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        ledger_path=str(ledger),
        live_enabled=live,
        openai_api_key="sk-test",
        typesafe_api_key="ts-test",
        allowed_hosts=["testserver"],
    )
    fakes = clients or FakeLiveClients()
    service = RunService(
        settings,
        data_dir=DATA,
        store=FileReplayStore(tmp_path / "replays"),
        live_factory=lambda s, g: fakes,
        guard_factory=lambda s: BudgetGuard(Ledger(ledger), cap=s.budget_cap_usd),
    )
    client = TestClient(create_app(settings=settings, service=service))
    client.__enter__()
    _OPEN.append(client)
    return client


def wait_done(client: TestClient, run_id: str) -> dict[str, Any]:
    for _ in range(200):
        body = client.get(f"/api/runs/{run_id}").json()["data"]
        if body["status"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def test_scenarios_list_and_detail_show_the_llm_prompt(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    listing = client.get("/api/scenarios").json()
    detail = client.get("/api/scenarios/s1_reconciliation").json()["data"]

    assert listing["success"] and listing["data"][0]["id"] == "s1_reconciliation"
    assert "verbatim" in detail["llm_prompt"]
    assert detail["models"] == {"jev": "jev-latest", "llm": "gpt-6-luna"}


def test_documents_endpoint_returns_all_thirteen(tmp_path: Path) -> None:
    docs = make_client(tmp_path).get("/api/scenarios/s1_reconciliation/documents").json()["data"]

    assert [d["doc_id"] for d in docs][:2] == ["msa", "inv-2026-01"] and len(docs) == 13


def test_unknown_scenario_is_a_404_envelope(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/api/scenarios/nope")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "data": None,
        "error": {"code": "UNKNOWN_SCENARIO", "message": "Unknown scenario 'nope'"},
    }


def test_live_run_then_replay_through_the_api(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    started = client.post("/api/runs", json={"scenario_id": "s1_reconciliation", "mode": "live"})
    assert started.status_code == 202
    live = wait_done(client, started.json()["data"]["run_id"])
    assert live["status"] == "completed"
    assert live["result"]["sides"]["jev"]["scorecard"]["correct"] == 14

    recordings = client.get("/api/scenarios/s1_reconciliation/recordings").json()["data"]
    assert [r["id"] for r in recordings] == [live["result"]["recording_id"]]

    replay = client.post(
        "/api/runs", json={"scenario_id": "s1_reconciliation", "mode": "replay", "pace": False}
    )
    done = wait_done(client, replay.json()["data"]["run_id"])
    assert done["result"]["sides"]["llm"]["provenance"]["kind"] == "recorded"


def test_events_stream_as_server_sent_events(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    run_id = client.post(
        "/api/runs", json={"scenario_id": "s1_reconciliation", "mode": "live"}
    ).json()["data"]["run_id"]

    with client.stream("GET", f"/api/runs/{run_id}/events") as stream:
        assert stream.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[6:]) for line in stream.iter_lines() if line.startswith("data: ")]

    assert events[0]["type"] == "run_started" and events[-1]["type"] == "run_completed"
    assert [e["seq"] for e in events] == list(range(len(events)))


def test_live_is_refused_when_disabled(tmp_path: Path) -> None:
    response = make_client(tmp_path, live=False).post(
        "/api/runs", json={"scenario_id": "s1_reconciliation", "mode": "live"}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LIVE_DISABLED"


def test_over_budget_live_run_is_refused_before_it_starts(tmp_path: Path) -> None:
    clients = FakeLiveClients(llm=FakeLiveLlm(per_call=Decimal("4.90")))
    client = make_client(tmp_path, clients=clients)

    response = client.post("/api/runs", json={"scenario_id": "s1_reconciliation", "mode": "live"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "BUDGET_EXCEEDED"
    assert clients.llm.inner.requests == [] and clients.closed == 1
    again = client.post("/api/runs", json={"scenario_id": "s1_reconciliation", "mode": "live"})
    assert again.json()["error"]["code"] == "BUDGET_EXCEEDED"  # the live slot was released


def test_replay_without_recordings_is_a_404(tmp_path: Path) -> None:
    response = make_client(tmp_path).post(
        "/api/runs", json={"scenario_id": "s1_reconciliation", "mode": "replay"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NO_RECORDING"


@pytest.mark.parametrize(
    "body",
    [
        {"scenario_id": "s1_reconciliation", "mode": "turbo"},
        {"mode": "live"},
        {"scenario_id": "s1_reconciliation", "mode": "replay", "recording_id": "../x"},
    ],
)
def test_invalid_run_requests_are_rejected(tmp_path: Path, body: dict[str, Any]) -> None:
    response = make_client(tmp_path).post("/api/runs", json=body)

    assert response.status_code in (404, 422)
    assert response.json()["success"] is False


def test_unknown_run_is_a_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    assert client.get("/api/runs/nope").status_code == 404
    assert client.get("/api/runs/nope/events").status_code == 404


def test_budget_shows_spend_by_fingerprint_never_keys(tmp_path: Path) -> None:
    body = make_client(tmp_path).get("/api/budget").json()

    assert body["success"] and body["data"]["ledger_initialised"] is True
    providers = {p["provider"]: p for p in body["data"]["providers"]}
    assert providers["openai"]["cap"] == "5.00" and providers["openai"]["spent"] == "0"
    assert "sk-test" not in json.dumps(body) and "ts-test" not in json.dumps(body)


def test_untrusted_host_header_is_rejected(tmp_path: Path) -> None:
    response = make_client(tmp_path).get("/api/health", headers={"host": "evil.example"})

    assert response.status_code == 400


def test_cors_allows_only_the_local_web_app(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    ok = client.options(
        "/api/health",
        headers={"origin": "http://localhost:5173", "access-control-request-method": "GET"},
    )
    bad = client.options(
        "/api/health",
        headers={"origin": "https://evil.example", "access-control-request-method": "GET"},
    )

    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


async def test_concurrent_live_starts_cannot_both_pass_the_one_run_check(tmp_path: Path) -> None:
    import asyncio

    import httpx

    ledger = tmp_path / "ledger.jsonl"
    initialised_ledger(ledger)
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        ledger_path=str(ledger),
        live_enabled=True,
        openai_api_key="sk-test",
        typesafe_api_key="ts-test",
        allowed_hosts=["testserver"],
    )

    def slow_factory(s: Settings, g: BudgetGuard) -> FakeLiveClients:
        time.sleep(0.2)  # prepare_live runs in a thread; widen the race window
        return FakeLiveClients()

    service = RunService(
        settings,
        data_dir=DATA,
        store=FileReplayStore(tmp_path / "replays"),
        live_factory=slow_factory,
        guard_factory=lambda s: BudgetGuard(Ledger(ledger), cap=s.budget_cap_usd),
    )
    app = create_app(settings=settings, service=service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        body = {"scenario_id": "s1_reconciliation", "mode": "live"}
        first, second = await asyncio.gather(
            client.post("/api/runs", json=body), client.post("/api/runs", json=body)
        )

    assert sorted([first.status_code, second.status_code]) == [202, 409]
