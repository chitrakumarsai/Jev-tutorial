"""`jev.cli budget show`: spend, cap and headroom per provider, read-only, never a key."""

from decimal import Decimal
from pathlib import Path

import pytest

from jev.budget.guard import BudgetGuard, key_fingerprint
from jev.cli import main
from tests.helpers import initialised_ledger

OPENAI_KEY = "sk-test-openai-key-1234567890"
TYPESAFE_KEY = "ts-test-typesafe-key-0987654321"


@pytest.fixture
def ledger_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "ledger.jsonl"
    monkeypatch.setenv("LEDGER_PATH", str(path))
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.setenv("TYPESAFE_API_KEY", TYPESAFE_KEY)
    return path


def test_shows_spent_cap_and_headroom_per_provider_without_any_key(
    ledger_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    guard = BudgetGuard(initialised_ledger(ledger_path), cap=Decimal("5.00"))
    fp = key_fingerprint(OPENAI_KEY)
    guard.commit(
        guard.reserve("openai", fp, Decimal("0.10"), run_id="r1"), actual=Decimal("0.0423")
    )

    assert main(["budget", "show"]) == 0

    out = capsys.readouterr().out
    assert "openai: spent $0.0423 of $5.00" in out
    assert "typesafe: spent $0.0000 of $5.00" in out
    assert "remaining" in out
    assert OPENAI_KEY not in out and TYPESAFE_KEY not in out
    assert fp not in out  # not even the fingerprint


def test_says_which_key_is_missing(
    ledger_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    initialised_ledger(ledger_path)
    monkeypatch.setenv("TYPESAFE_API_KEY", "")

    assert main(["budget", "show"]) == 0

    assert "typesafe: no key configured" in capsys.readouterr().out


def test_a_missing_ledger_is_reported_not_created(
    ledger_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["budget", "show"]) == 1

    assert "budget init" in capsys.readouterr().err
    assert not ledger_path.exists()


def test_a_corrupt_ledger_is_reported_without_a_traceback_or_a_key(
    ledger_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger_path.write_text(f"garbage {OPENAI_KEY}\n", encoding="utf-8")

    assert main(["budget", "show"]) == 1

    captured = capsys.readouterr()
    assert "corrupt" in captured.err and "Traceback" not in captured.err
    assert OPENAI_KEY not in captured.err + captured.out


def test_show_leaves_the_ledger_byte_for_byte_unchanged(
    ledger_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    guard = BudgetGuard(initialised_ledger(ledger_path), cap=Decimal("5.00"))
    guard.reserve("openai", key_fingerprint(OPENAI_KEY), Decimal("0.02"), run_id="r1")
    before = ledger_path.read_bytes()

    assert main(["budget", "show"]) == 0

    assert ledger_path.read_bytes() == before
    out = capsys.readouterr().out
    assert "reserved $0.0200" in out
    assert "typesafe: spent $0.0000 of $5.00" in out


def test_a_whitespace_only_key_counts_as_missing(
    ledger_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    initialised_ledger(ledger_path)
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    assert main(["budget", "show"]) == 0

    out = capsys.readouterr().out
    assert "openai: no key configured (cap $5.00)" in out
    assert "typesafe: spent $0.0000 of $5.00" in out
