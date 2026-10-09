"""Recording wrappers (live → file) and replay clients (file → pipeline), per provider."""

import asyncio
from collections import defaultdict, deque
from typing import TypeVar

from pydantic import BaseModel

from jev.providers.jev.port import JevPort
from jev.providers.jev.types import JevRequest, JevResult
from jev.providers.openai.port import LlmPort
from jev.providers.openai.types import LlmRequest, LlmResult
from jev.replay.hashing import request_hash
from jev.replay.models import RecordedCall, Recording, ReplayProvider

T = TypeVar("T", bound=BaseModel)


class ReplayStaleError(RuntimeError):
    """The pipeline asked for something that was never recorded. Never falls back to live."""


class RecordingJevClient:
    def __init__(self, inner: JevPort, *, model: str) -> None:
        self._inner = inner
        self._model = model
        self.calls: list[RecordedCall] = []

    async def evaluate(self, request: JevRequest) -> JevResult:
        result = await self._inner.evaluate(request)
        self.calls.append(
            RecordedCall(
                request_hash=request_hash(request.payload(self._model)),
                provider="typesafe",
                purpose=request.purpose,
                model=self._model,
                latency_ms=result.latency_ms,
                result=result.model_dump(mode="json"),
            )
        )
        return result


class RecordingLlmClient:
    def __init__(self, inner: LlmPort, *, model: str) -> None:
        self._inner = inner
        self._model = model
        self.calls: list[RecordedCall] = []

    async def parse(self, request: LlmRequest, schema: type[T]) -> LlmResult[T]:
        result = await self._inner.parse(request, schema)
        self.calls.append(
            RecordedCall(
                request_hash=request_hash(request.payload(self._model, schema)),
                provider="openai",
                purpose=request.purpose,
                model=self._model,
                latency_ms=result.latency_ms,
                result=result.model_dump(mode="json"),
            )
        )
        return result


class _ReplayIndex:
    """Serves recorded calls by request hash, in recorded order for repeated requests."""

    def __init__(self, recording: Recording, provider: ReplayProvider) -> None:
        self._queues: dict[str, deque[RecordedCall]] = defaultdict(deque)
        for call in recording.calls:
            if call.provider == provider:
                self._queues[call.request_hash].append(call)
        self._recording_id = recording.id

    def next(self, digest: str, purpose: str) -> RecordedCall:
        queue = self._queues.get(digest)
        if not queue:
            raise ReplayStaleError(
                f"No recorded answer for '{purpose}' in recording {self._recording_id}. "
                "The pipeline or documents changed since recording: re-record this scenario."
            )
        return queue.popleft()


async def _pace(call: RecordedCall, pace: bool) -> None:
    """Optionally wait the recorded latency so a replay animates with its original timing."""
    if pace:
        await asyncio.sleep(call.latency_ms / 1000)


class ReplayJevClient:
    def __init__(self, recording: Recording, *, pace: bool = False) -> None:
        self._model = recording.jev_model
        self._index = _ReplayIndex(recording, "typesafe")
        self._pace = pace

    async def evaluate(self, request: JevRequest) -> JevResult:
        call = self._index.next(request_hash(request.payload(self._model)), request.purpose)
        await _pace(call, self._pace)
        return JevResult.model_validate(call.result)


class ReplayLlmClient:
    def __init__(self, recording: Recording, *, pace: bool = False) -> None:
        self._model = recording.llm_model
        self._index = _ReplayIndex(recording, "openai")
        self._pace = pace

    async def parse(self, request: LlmRequest, schema: type[T]) -> LlmResult[T]:
        call = self._index.next(request_hash(request.payload(self._model, schema)), request.purpose)
        await _pace(call, self._pace)
        return LlmResult[schema].model_validate(call.result)  # type: ignore[valid-type]
