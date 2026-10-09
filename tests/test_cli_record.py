"""`jev.cli record`: shows the worst-case cost, needs a typed confirmation, then records."""

from pathlib import Path

import pytest

from jev.cli import record
from jev.replay.store import FileReplayStore
from tests.runs.test_service import service


def test_record_needs_typed_confirmation_and_saves_recordings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompts: list[str] = []

    def confirm(prompt: str) -> str:
        prompts.append(prompt)
        return "RECORD"

    code = record(service(tmp_path), runs=2, input_fn=confirm)

    assert code == 0
    assert "worst case" in prompts[0] and "openai" in prompts[0] and "typesafe" in prompts[0]
    assert len(FileReplayStore(tmp_path / "replays").list_recordings("s1_reconciliation")) == 2
    out = capsys.readouterr().out
    assert "Jev 14/14" in out and "Recorded" in out


def test_anything_but_record_cancels_without_spending(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = record(service(tmp_path), runs=1, input_fn=lambda prompt: "yes")

    assert code == 1
    assert FileReplayStore(tmp_path / "replays").list_recordings("s1_reconciliation") == []
    assert "Cancelled" in capsys.readouterr().err


def test_refusals_are_reported_not_raised(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from decimal import Decimal

    from tests.runs.test_service import FakeLiveClients, FakeLiveLlm

    over = service(tmp_path, FakeLiveClients(llm=FakeLiveLlm(per_call=Decimal("4.90"))))

    assert record(over, runs=1, input_fn=lambda prompt: "RECORD") == 1
    assert "Refused" in capsys.readouterr().err


def test_runs_must_be_between_one_and_five(tmp_path: Path) -> None:
    svc = service(tmp_path)

    with pytest.raises(ValueError):
        record(svc, runs=0, input_fn=lambda prompt: "RECORD")
    with pytest.raises(ValueError):
        record(svc, runs=6, input_fn=lambda prompt: "RECORD")


def test_prompt_shows_the_total_worst_case_for_all_runs(tmp_path: Path) -> None:
    prompts: list[str] = []

    record(service(tmp_path), runs=3, input_fn=lambda p: prompts.append(p) or "no")

    assert "total worst case" in prompts[0] and "$0.0690" in prompts[0]  # 3 x (13x0.001 + 0.01)


def test_a_prompt_that_cannot_be_answered_cancels_and_closes_clients(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.runs.test_service import FakeLiveClients

    clients = FakeLiveClients()

    def no_tty(prompt: str) -> str:
        raise EOFError

    assert record(service(tmp_path, clients), runs=1, input_fn=no_tty) == 1
    assert clients.closed == 1 and "Cancelled" in capsys.readouterr().err


def test_a_failed_run_is_reported_with_a_spend_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.runs.test_service import FakeLiveClients, FakeLiveLlm, _FailingLlm
    from tests.s1.test_llm_pipeline import perfect_report

    clients = FakeLiveClients(llm=FakeLiveLlm(inner=_FailingLlm(perfect_report())))

    assert record(service(tmp_path, clients), runs=2, input_fn=lambda p: "RECORD") == 1
    err = capsys.readouterr().err
    assert "Run 1/2 failed (RuntimeError)" in err and "may have been spent" in err


@pytest.mark.parametrize("runs", ["0", "6", "x"])
def test_cli_rejects_out_of_range_runs_before_anything_else(runs: str) -> None:
    from jev.cli import main

    with pytest.raises(SystemExit) as exit_info:
        main(["record", "s1", "--runs", runs])
    assert exit_info.value.code == 2
