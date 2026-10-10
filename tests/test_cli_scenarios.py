"""CLI commands work per scenario: validate one or all, and record by full id or short alias."""

from dataclasses import replace

import pytest

from jev import cli
from jev.cli import main, scenario_arg
from jev.scenarios.registry import SCENARIOS
from jev.scenarios.s1_reconciliation.documents import SCENARIO_ID
from tests.s1.facts import DATA


def test_validate_checks_every_registered_scenario_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["data", "validate", "--data-dir", str(DATA)]) == 0

    out = capsys.readouterr().out
    for spec in SCENARIOS:
        assert f"OK: {spec.id} documents and answer key are consistent." in out


def test_validate_can_check_one_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["data", "validate", "--data-dir", str(DATA), "--scenario", SCENARIO_ID])

    assert code == 0
    assert SCENARIO_ID in capsys.readouterr().out


@pytest.mark.parametrize("name", ["s1", SCENARIO_ID])
def test_a_scenario_is_named_by_full_id_or_short_alias(name: str) -> None:
    assert scenario_arg(name).id == SCENARIO_ID


def test_one_failing_scenario_fails_validation_without_hiding_the_others(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = replace(
        SCENARIOS[0], id="broken", alias="b", validate_data=lambda _: ["key item K9 not found"]
    )
    monkeypatch.setattr(cli, "SCENARIOS", (*SCENARIOS, broken))

    code = main(["data", "validate", "--data-dir", str(DATA)])

    captured = capsys.readouterr()
    assert code == 1
    assert f"OK: {SCENARIO_ID}" in captured.out
    assert "broken: key item K9 not found" in captured.err


def test_an_unknown_scenario_is_refused_before_anything_runs() -> None:
    with pytest.raises(SystemExit):
        main(["record", "nope", "--runs", "1"])
