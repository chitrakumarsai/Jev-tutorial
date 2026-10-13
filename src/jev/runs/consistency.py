"""Consistency ×3 (PLAN-P7): replay a scenario's recorded live runs (no live calls, no
spend) and show, per answer-key item and side, what each run answered and whether it changed.
Replaying one recording three times would be trivially identical, so separate recordings are
used, newest three, shown oldest first."""

import asyncio
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, computed_field

from jev.domain.findings import Finding
from jev.replay.models import RecordingMeta
from jev.runs.models import RunResult, SideResult
from jev.runs.service import NoRecordingError, RunService
from jev.scoring.scorecard import ItemStatus

RUNS = 3
MISSED = "—"


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ItemConsistency(_Frozen):
    key_id: str
    label: str
    answers: tuple[str, ...]  # one per run, in run order
    statuses: tuple[ItemStatus, ...]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def changed(self) -> bool:
        return len(set(self.answers)) > 1


class SideConsistency(_Frozen):
    items: tuple[ItemConsistency, ...]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def changed(self) -> int:
        return sum(item.changed for item in self.items)


class ConsistencyReport(_Frozen):
    scenario_id: str
    recordings: tuple[RecordingMeta, ...]  # oldest first
    sides: dict[str, SideConsistency]


def _answer(finding: Finding | None) -> str:
    """What a side answered for one item, as a short, comparable string."""
    if finding is None:
        return MISSED
    if finding.verdict is not None:
        return f"{finding.verdict} · {finding.risk}" if finding.risk else finding.verdict
    if finding.variance is None:
        return MISSED
    return format(finding.variance.normalize(), "f")  # 100.00, 100.0 and 1E+2 compare equal


def _side(results: Sequence[SideResult]) -> SideConsistency:
    """Runs are matched by answer-key id, never by position."""
    by_key = [{item.key_id: item for item in r.scorecard.items} for r in results]
    found = [{f.id: f for f in r.findings} for r in results]
    items = []
    for item in results[0].scorecard.items:
        scored = [run.get(item.key_id) for run in by_key]
        if any(s is None for s in scored):
            raise ValueError(f"Key item {item.key_id} is missing from a recorded run")
        items.append(
            ItemConsistency(
                key_id=item.key_id,
                label=item.label or item.key_id,
                answers=tuple(
                    _answer(f.get(s.finding_id or ""))
                    for f, s in zip(found, scored, strict=True)
                    if s
                ),
                statuses=tuple(s.status for s in scored if s),
            )
        )
    return SideConsistency(items=tuple(items))


async def consistency(service: RunService, runs: int = RUNS) -> ConsistencyReport:
    # Listing reads every recording file: keep it off the event loop.
    metas = (await asyncio.to_thread(service.recordings))[:runs]  # newest first
    if not metas:
        raise NoRecordingError(f"No recordings for {service.scenario.id} yet.")
    ordered = sorted(metas, key=lambda m: m.recorded_at)
    results: list[RunResult] = []
    for n, meta in enumerate(ordered, start=1):
        results.append(
            await service.replay(
                f"consistency-{n}", recording_id=meta.id, on_event=lambda e: None, pace=False
            )
        )
    sides = {side: _side([r.sides[side] for r in results]) for side in ("jev", "llm")}
    return ConsistencyReport(
        scenario_id=service.scenario.id, recordings=tuple(ordered), sides=sides
    )
