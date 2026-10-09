"""Test-wide safety: tests never run in live mode and never reach the network."""

import socket
from typing import Any

import pytest

_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _blocked_create_connection(address: tuple[str, int], *args: Any, **kwargs: Any) -> Any:
    raise RuntimeError(f"Network access is blocked in tests (tried {address[0]}:{address[1]})")


@pytest.fixture(autouse=True)
def _force_replay_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LIVE_ENABLED", "false")
    # Keys exported in a developer's shell must not leak into tests (or change their result).
    for key in ("TYPESAFE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    real_connect = socket.socket.connect

    def guarded_connect(self: socket.socket, address: Any) -> Any:
        if self.family == socket.AF_UNIX:
            return real_connect(self, address)
        host = address[0] if isinstance(address, tuple) else address
        if host in _LOCAL_HOSTS:
            return real_connect(self, address)
        raise RuntimeError(f"Network access is blocked in tests (tried {address!r})")

    monkeypatch.setattr(socket, "create_connection", _blocked_create_connection)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
