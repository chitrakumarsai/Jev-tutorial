"""The interface every LLM client (live, recording, replay, fake) implements."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

from jev.providers.openai.types import LlmRequest, LlmResult

T = TypeVar("T", bound=BaseModel)


class LlmPort(Protocol):
    async def parse(self, request: LlmRequest, schema: type[T]) -> LlmResult[T]: ...
