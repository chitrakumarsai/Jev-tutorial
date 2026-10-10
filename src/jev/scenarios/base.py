"""What every scenario side produces, and how it reports progress."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from jev.domain.findings import Finding
from jev.providers.jev.port import JevPort
from jev.providers.jev.types import JevRequest
from jev.providers.openai.port import LlmPort
from jev.providers.openai.types import LlmRequest
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


class JevSidePipeline(Protocol):
    """The Jev + code side of a scenario. `requests()` does no I/O (used for pre-flight)."""

    def requests(self) -> Sequence[JevRequest]: ...
    async def run(self, jev: JevPort, emit: EventSink) -> SideOutput: ...


class LlmSidePipeline(Protocol):
    """The plain-LLM side of a scenario: one request, built without I/O."""

    def request(self) -> LlmRequest: ...
    async def run(self, llm: LlmPort, emit: EventSink) -> SideOutput: ...
