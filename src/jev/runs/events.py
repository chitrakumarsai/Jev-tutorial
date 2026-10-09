"""Ordered, timestamped events. The UI animates from these, live or replayed."""

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

EventType = Literal["run_started", "step", "finding", "side_completed", "run_completed", "error"]


class RunEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    seq: int
    t_ms: int  # since the run started
    type: EventType
    side: Literal["jev", "llm"] | None = None
    data: dict[str, Any]


OnEvent = Callable[[RunEvent], None]
