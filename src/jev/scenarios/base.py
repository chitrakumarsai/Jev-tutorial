"""What every scenario side produces, and how it reports progress."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from jev.domain.findings import Finding
from jev.scoring.metrics import CallUsage

Side = Literal["jev", "llm"]
# emit(event_type, side, data): "step" | "finding" events drive the UI animation.
EventSink = Callable[[str, Side | None, dict[str, Any]], None]


@dataclass(frozen=True)
class SideOutput:
    findings: tuple[Finding, ...]
    usages: tuple[CallUsage, ...]
    models: tuple[str, ...]  # resolved model ids that answered
    notes: tuple[str, ...] = ()  # e.g. "contract term not found": shown, never silently dropped
