"""Test-wide safety: tests never run in live mode, whatever the shell environment says."""

import pytest


@pytest.fixture(autouse=True)
def _force_replay_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_ENABLED", "false")
