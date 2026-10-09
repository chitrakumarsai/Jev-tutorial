"""The web tests play a real replay's events (and show its documents) from fixtures; keep them
in step with the backend.

Regenerate: uv run python -m tests.api.test_event_fixture
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from jev.config import Settings
from jev.runs.events import RunEvent
from jev.runs.service import RunService

FIXTURES = Path(__file__).parents[2] / "web" / "src" / "test" / "fixtures"
FIXTURE = FIXTURES / "s1-replay-events.json"
DOCS_FIXTURE = FIXTURES / "s1-documents.json"
RUN_ID = "run-fixture"


def replay_events(recording_id: str | None) -> list[dict[str, Any]]:
    events: list[RunEvent] = []
    service = RunService(Settings(_env_file=None))  # type: ignore[call-arg]
    asyncio.run(
        service.replay(RUN_ID, recording_id=recording_id, on_event=events.append, pace=False)
    )
    return [event.model_dump(mode="json") for event in events]


def documents() -> list[dict[str, str]]:
    """As `GET /api/scenarios/{id}/documents` returns them."""
    docs = RunService(Settings(_env_file=None)).documents.documents  # type: ignore[call-arg]
    return [{"doc_id": d.doc_id, "text": d.text} for d in docs]


def _timeless(event: dict[str, Any]) -> str:
    """Order and wall-clock timings vary between replays (concurrent requests); content doesn't."""
    event = json.loads(json.dumps(event))  # a copy: the zeroing below mustn't touch the input
    data = event["data"]
    if "result" in data:
        sides = data["result"].get("sides", {"_": data["result"]})
        for side in sides.values():
            side["metrics"]["latency_ms"] = 0
    return json.dumps({**event, "seq": 0, "t_ms": 0}, sort_keys=True)


def test_fixture_matches_a_fresh_replay() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    recording_id = fixture[-1]["data"]["result"]["recording_id"]

    fresh = replay_events(recording_id)

    # Order varies between replays, but the frame of a run does not.
    assert [event["seq"] for event in fresh] == list(range(len(fresh)))
    assert fresh[0]["type"] == "run_started"
    assert fresh[-1]["type"] == "run_completed"
    assert sorted(map(_timeless, fixture)) == sorted(map(_timeless, fresh)), (
        "web fixture is stale: run `uv run python -m tests.api.test_event_fixture`"
    )


def test_fixture_is_one_complete_ordered_run() -> None:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert [event["seq"] for event in fixture] == list(range(len(fixture)))
    assert fixture[0]["type"] == "run_started"
    assert fixture[-1]["type"] == "run_completed"


def test_documents_fixture_matches_the_scenario() -> None:
    assert json.loads(DOCS_FIXTURE.read_text(encoding="utf-8")) == documents(), (
        "web documents fixture is stale: run `uv run python -m tests.api.test_event_fixture`"
    )


if __name__ == "__main__":  # pragma: no cover - regeneration helper
    FIXTURES.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(replay_events(None), indent=2) + "\n", encoding="utf-8")
    DOCS_FIXTURE.write_text(json.dumps(documents(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {FIXTURE} and {DOCS_FIXTURE}.")
