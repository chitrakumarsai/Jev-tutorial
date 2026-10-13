"""Consistency ×3 (PLAN-P7): replay a scenario's recorded live runs (no live calls, no
spend) and show, per answer-key item and side, what each run answered and whether it changed.
Replaying one recording three times would be trivially identical, so separate recordings are
used, newest three, shown oldest first."""

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
    return str(finding.variance) if finding.variance is not None else MISSED


def _side(results: Sequence[SideResult]) -> SideConsistency:
    first = results[0].scorecard.items
    items = []
    for index, item in enumerate(first):
        answers, statuses = [], []
        for result in results:
            scored = result.scorecard.items[index]
            found = {f.id: f for f in result.findings}
            answers.append(_answer(found.get(scored.finding_id or "")))
            statuses.append(scored.status)
        items.append(
            ItemConsistency(
                key_id=item.key_id,
                label=item.label or item.key_id,
                answers=tuple(answers),
                statuses=tuple(statuses),
            )
        )
    return SideConsistency(items=tuple(items))


async def consistency(service: RunService, runs: int = RUNS) -> ConsistencyReport:
    metas = service.recordings()[:runs]  # newest first
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
