"""Ordered, timestamped events. The UI animates from these, live or replayed."""

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# `run_failed`, not `error`: a named SSE `error` event would clash with EventSource's own.
EventType = Literal[
    "run_started", "step", "finding", "side_completed", "run_completed", "run_failed"
]


class RunEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    seq: int
    t_ms: int  # since the run started
    type: EventType
    side: Literal["jev", "llm"] | None = None
    data: dict[str, Any]


OnEvent = Callable[[RunEvent], None]
