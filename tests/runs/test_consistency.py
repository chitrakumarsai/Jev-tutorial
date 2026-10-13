"""Consistency ×3: replay a scenario's recorded live runs (no spend) and show, per answer-key
item and side, what each run answered and whether it changed."""

import pytest

from jev.config import Settings
from jev.replay.store import FileReplayStore
from jev.runs.consistency import consistency
from jev.runs.service import NoRecordingError, RunService
from jev.scenarios.registry import get_scenario
from tests.s1.facts import DATA


def service(alias: str, replays_dir: str = "replays") -> RunService:
    spec = get_scenario(alias)
    assert spec is not None
    return RunService(
        Settings(_env_file=None),  # type: ignore[call-arg]
        scenario=spec,
        data_dir=DATA,
        store=FileReplayStore(DATA / replays_dir),
    )


async def test_s3_shows_jev_unchanged_and_the_llm_changing_on_c5() -> None:
    report = await consistency(service("s3"))

    assert len(report.recordings) == 3
    jev, llm = report.sides["jev"], report.sides["llm"]
    assert jev.changed == 0
    assert [i.label for i in llm.items if i.changed] == ["C5"]
    c5 = next(i for i in llm.items if i.label == "C5")
    assert len(c5.answers) == 3 and len(set(c5.answers)) == 2
    assert "unsupported" in c5.answers and "verified" in c5.answers


async def test_s2_answers_carry_verdict_and_risk_and_jev_never_changes() -> None:
    report = await consistency(service("s2"))

    jev = report.sides["jev"]
    assert jev.changed == 0
    breach = next(i for i in jev.items if i.label == "Security breach notification")
    assert breach.answers == ("absent · critical",) * 3
    assert all(s in ("correct", "correct_in_review") for s in breach.statuses)


async def test_s1_answers_are_the_reported_variances() -> None:
    report = await consistency(service("s1"))

    jev = report.sides["jev"]
    assert jev.changed == 0 and len(jev.items) == 14
    assert all(len(set(i.answers)) == 1 for i in jev.items)
    assert all(answer.replace(".", "").lstrip("-").isdigit() for answer in jev.items[0].answers)


async def test_runs_are_listed_oldest_first_with_their_provenance() -> None:
    report = await consistency(service("s3"))

    dates = [r.recorded_at for r in report.recordings]
    assert dates == sorted(dates)
    assert all(r.jev_model and r.llm_model for r in report.recordings)


async def test_a_scenario_without_recordings_is_refused(tmp_path: object) -> None:
    with pytest.raises(NoRecordingError):
        await consistency(service("s3", replays_dir="no_such_dir"))
