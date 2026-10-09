import socket
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from jev.config import HARD_BUDGET_CAP_USD, PROJECT_ROOT, Settings


def make(**overrides: object) -> Settings:
    # _env_file=None: never read a real dotenv file in tests.
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


def test_safe_defaults() -> None:
    settings = make()

    assert settings.live_enabled is False
    assert settings.openai_model == "gpt-6-luna"
    assert settings.jev_model == "jev-latest"
    assert settings.budget_cap_usd == Decimal("5.00")
    assert settings.review_threshold == 0.8
    assert settings.ledger_path == PROJECT_ROOT / "var" / "ledger.jsonl"
    assert settings.typesafe_api_key is None
    assert settings.openai_api_key is None


def test_cap_may_be_lowered_but_never_raised() -> None:
    assert make(budget_cap_usd="1.50").budget_cap_usd == Decimal("1.50")
    assert Decimal("5.00") == HARD_BUDGET_CAP_USD

    with pytest.raises(ValidationError):
        make(budget_cap_usd="5.01")
    with pytest.raises(ValidationError):
        make(budget_cap_usd="0")


@pytest.mark.parametrize("threshold", [-0.1, 0.0, 1.5])
def test_review_threshold_must_be_a_probability(threshold: float) -> None:
    with pytest.raises(ValidationError):
        make(review_threshold=threshold)


def test_keys_are_secret_and_never_rendered() -> None:
    settings = make(openai_api_key="sk-test-123", typesafe_api_key="ts-test-456")

    assert "sk-test-123" not in repr(settings)
    assert "ts-test-456" not in str(settings.model_dump())
    assert settings.openai_api_key is not None
    assert settings.openai_api_key.get_secret_value() == "sk-test-123"


def test_environment_variables_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6-luna")
    monkeypatch.setenv("BUDGET_CAP_USD", "2.00")

    assert make().budget_cap_usd == Decimal("2.00")


def test_tests_run_in_replay_mode_even_if_shell_says_live() -> None:
    # tests/conftest.py forces LIVE_ENABLED=false for every test.
    assert make().live_enabled is False


def test_network_is_blocked_in_tests() -> None:
    with pytest.raises(RuntimeError, match="Network access is blocked"):
        socket.create_connection(("example.com", 443), timeout=1)


def test_relative_ledger_path_is_anchored_to_the_project_not_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert make(ledger_path="var/other.jsonl").ledger_path == PROJECT_ROOT / "var" / "other.jsonl"
    assert make(ledger_path=str(tmp_path / "x.jsonl")).ledger_path == tmp_path / "x.jsonl"
    assert (PROJECT_ROOT / "pyproject.toml").is_file()
