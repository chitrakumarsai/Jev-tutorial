"""Golden: every committed S2 recording replays through today's pipeline (none is stale), Jev
matches the key on every clause, and its answers are the same on every recorded run."""

import json
from pathlib import Path

import pytest

from jev.config import Settings
from jev.replay.store import FileReplayStore
from jev.runs.models import RunResult
from jev.runs.service import RunService
from jev.scenarios.registry import get_scenario
from jev.scenarios.s2_clause_review.llm_pipeline import MAX_OUTPUT_TOKENS
from tests.s1.facts import DATA

RECORDINGS = sorted((DATA / "replays" / "s2_clause_review").glob("*.json"))


async def _replay(recording_id: str) -> RunResult:
    spec = get_scenario("s2")
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


def test_s2_has_recordings_to_replay() -> None:
    assert len(RECORDINGS) >= 3


@pytest.mark.parametrize("path", RECORDINGS, ids=[p.stem for p in RECORDINGS])
async def test_s2_recording_replays_and_jev_matches_every_clause(path: Path) -> None:
    result = await _replay(path.stem)

    jev = result.sides["jev"]
    assert (jev.scorecard.correct + jev.scorecard.correct_in_review, jev.scorecard.of) == (10, 10)
    assert {f.kind for f in jev.findings if f.lane == "review"} == {"audit_rights", "insurance"}
    llm = result.sides["llm"]
    assert llm.scorecard.of == 10
    output = llm.metrics.output_tokens
    assert output is not None and output < MAX_OUTPUT_TOKENS / 2  # no truncation risk


async def test_jev_gives_the_same_answers_on_every_recorded_run() -> None:
    answer_sets = set()
    for path in RECORDINGS:
        result = await _replay(path.stem)
        findings = result.sides["jev"].findings
        answer_sets.add(json.dumps([(f.kind, f.verdict, f.risk, f.line_ref) for f in findings]))

    assert len(answer_sets) == 1
