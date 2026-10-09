"""Run results as returned by the API."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from jev.domain.findings import Finding
from jev.scoring.metrics import Metrics
from jev.scoring.scorecard import Scorecard

Mode = Literal["live", "replay"]


class Provenance(BaseModel):
    """Where answers came from. Replays are always labelled as recorded."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["live", "recorded"]
    models: tuple[str, ...]
    recording_id: str | None = None
    recorded_at: str | None = None


class SideResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    side: Literal["jev", "llm"]
    findings: tuple[Finding, ...]
    metrics: Metrics
    scorecard: Scorecard
    provenance: Provenance
    notes: tuple[str, ...] = ()


class RunResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: str
    scenario_id: str
    mode: Mode
    sides: dict[str, SideResult]
    recording_id: str | None = None
