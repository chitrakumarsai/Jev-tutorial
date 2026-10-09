"""Recording file format. Results only: no request headers, no API keys."""

import uuid
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ReplayProvider = Literal["typesafe", "openai"]
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecordedCall(_Frozen):
    request_hash: str
    provider: ReplayProvider
    purpose: str
    model: str  # the configured model the request was hashed with
    latency_ms: int
    result: JsonValue  # our typed result (JevResult / LlmResult), as recorded from the live call


class RecordingMeta(_Frozen):
    id: str = Field(pattern=ID_PATTERN)
    scenario_id: str = Field(pattern=ID_PATTERN)
    recorded_at: str
    jev_model: str
    llm_model: str


class Recording(RecordingMeta):
    calls: tuple[RecordedCall, ...]

    @classmethod
    def create(
        cls,
        scenario_id: str,
        *,
        jev_model: str,
        llm_model: str,
        calls: tuple[RecordedCall, ...] | list[RecordedCall],
        recorded_at: str | None = None,
    ) -> Self:
        stamp = recorded_at or datetime.now(UTC).isoformat()
        compact = datetime.fromisoformat(stamp).strftime("%Y%m%dT%H%M%SZ")
        return cls(
            id=f"{compact}-{uuid.uuid4().hex[:8]}",
            scenario_id=scenario_id,
            recorded_at=stamp,
            jev_model=jev_model,
            llm_model=llm_model,
            calls=tuple(calls),
        )

    def meta(self) -> RecordingMeta:
        return RecordingMeta(**self.model_dump(exclude={"calls"}))
