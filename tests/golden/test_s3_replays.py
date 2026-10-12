"""Golden: every committed S3 recording replays through today's pipeline (none is stale), Jev
never gives a wrong verdict, catches every planted error, and answers the same on every run."""

import json
from pathlib import Path

import pytest

from jev.config import Settings
from jev.replay.store import FileReplayStore
from jev.runs.models import RunResult
from jev.runs.service import RunService
from jev.scenarios.registry import get_scenario
from jev.scenarios.s3_citation_check.llm_pipeline import MAX_OUTPUT_TOKENS
from tests.s1.facts import DATA

RECORDINGS = sorted((DATA / "replays" / "s3_citation_check").glob("*.json"))


async def _replay(recording_id: str) -> RunResult:
    spec = get_scenario("s3")
    assert spec is not None
    service = RunService(
        Settings(_env_file=None),  # type: ignore[call-arg]
        scenario=spec,
        data_dir=DATA,
        store=FileReplayStore(DATA / "replays"),
    )
    return await service.replay(
        "golden", recording_id=recording_id, on_event=lambda event: None, pace=False
    )


def test_s3_has_recordings_to_replay() -> None:
    assert len(RECORDINGS) >= 3


@pytest.mark.parametrize("path", RECORDINGS, ids=[p.stem for p in RECORDINGS])
async def test_s3_recording_replays_and_jev_gets_every_verdict_right(path: Path) -> None:
    result = await _replay(path.stem)

    jev = result.sides["jev"].scorecard
    assert (jev.correct + jev.correct_in_review, jev.of) == (10, 10)
    summary = {row.label: row.value for row in jev.summary}
    assert summary["Planted errors caught"] == "3 of 3"
    assert summary["Wrong-section citation kept"] == "Yes"
    output = result.sides["llm"].metrics.output_tokens
    assert output is not None and output < MAX_OUTPUT_TOKENS / 2  # no truncation risk


async def test_jev_gives_the_same_verdicts_on_every_recorded_run() -> None:
    verdict_sets = set()
    for path in RECORDINGS:
        findings = (await _replay(path.stem)).sides["jev"].findings
        verdict_sets.add(json.dumps(sorted((f.id, f.verdict) for f in findings)))

    assert len(verdict_sets) == 1
