"""The interface every Jev client (live, recording, replay, fake) implements."""

from typing import Protocol

from jev.providers.jev.types import JevRequest, JevResult


class JevPort(Protocol):
    async def evaluate(self, request: JevRequest) -> JevResult: ...
