"""The web tests play a real replay's events from a fixture; keep it in step with the backend.

Regenerate: uv run python -m tests.api.test_event_fixture
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from jev.config import Settings
from jev.runs.events import RunEvent
from jev.runs.service import RunService

FIXTURE = Path(__file__).parents[2] / "web" / "src" / "test" / "fixtures" / "s1-replay-events.json"
RUN_ID = "run-fixture"


def replay_events(recording_id: str | None) -> list[dict[str, Any]]:
    events: list[RunEvent] = []
    service = RunService(Settings())
    asyncio.run(
        service.replay(RUN_ID, recording_id=recording_id, on_event=events.append, pace=False)
    )
    return [event.model_dump(mode="json") for event in events]


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


if __name__ == "__main__":  # pragma: no cover - regeneration helper
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(replay_events(None), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {FIXTURE}.")
