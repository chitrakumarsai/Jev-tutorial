"""Live clients can only be built when live mode is explicitly enabled and keys are present."""

from pathlib import Path

import pytest

from jev.config import Settings
from jev.providers.factory import (
    LiveDisabledError,
    MissingKeyError,
    build_guard,
    build_live_clients,
)
from tests.helpers import initialised_ledger


def settings(tmp_path: Path, **overrides: object) -> Settings:
    base: dict[str, object] = {"ledger_path": str(tmp_path / "ledger.jsonl")}
    return Settings(_env_file=None, **{**base, **overrides})  # type: ignore[arg-type]


def test_live_clients_are_refused_while_live_mode_is_off(tmp_path: Path) -> None:
    s = settings(tmp_path, openai_api_key="sk-a", typesafe_api_key="ts-b")

    with pytest.raises(LiveDisabledError, match="LIVE_ENABLED"):
        build_live_clients(s, build_guard(s))


def test_missing_keys_are_named_but_never_shown(tmp_path: Path) -> None:
    s = settings(tmp_path, live_enabled=True, openai_api_key="sk-secret-value")

    with pytest.raises(MissingKeyError) as info:
        build_live_clients(s, build_guard(s))

    assert "TYPESAFE_API_KEY" in str(info.value)
    assert "sk-secret-value" not in str(info.value)


async def test_enabled_with_keys_builds_both_clients(tmp_path: Path) -> None:
    initialised_ledger(tmp_path / "ledger.jsonl")
    s = settings(tmp_path, live_enabled=True, openai_api_key="sk-a", typesafe_api_key="ts-b")

    clients = build_live_clients(s, build_guard(s))

    assert clients.jev is not None and clients.llm is not None
    await clients.aclose()
