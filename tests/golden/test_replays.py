"""Golden: every committed recording still replays through today's pipeline (none is stale)."""

from pathlib import Path

import pytest

from jev.config import Settings
from jev.replay.store import FileReplayStore
from jev.runs.service import RunService
from tests.golden.test_jev_estimates import RECORDINGS
from tests.s1.facts import DATA


@pytest.mark.parametrize("path", RECORDINGS, ids=[p.stem for p in RECORDINGS])
async def test_committed_recording_replays_and_jev_is_exact(path: Path) -> None:
    service = RunService(
        Settings(_env_file=None),  # type: ignore[call-arg]
        data_dir=DATA,
        store=FileReplayStore(DATA / "replays"),
    )

    result = await service.replay(
        "golden", recording_id=path.stem, on_event=lambda event: None, pace=False
    )

    jev = result.sides["jev"].scorecard
    assert (jev.correct, jev.of, jev.total_variance_exact) == (14, 14, True)
    assert result.sides["llm"].scorecard.of == 14
