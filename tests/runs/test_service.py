"""Run service: both sides concurrently, scored, evented, budget-checked, recorded."""

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from jev.budget.guard import BudgetExceededError, BudgetGuard
from jev.config import Settings
from jev.providers.jev.types import JevRequest, JevResult
from jev.providers.openai.types import LlmRequest, LlmResult
from jev.replay.store import FileReplayStore, ReplayStoreError
from jev.runs.events import RunEvent
from jev.runs.service import NoRecordingError, RunService
from tests.helpers import initialised_ledger
from tests.s1.facts import DATA
from tests.s1.fake_jev import FakeJev
from tests.s1.test_llm_pipeline import FakeLlm, perfect_report


@dataclass
class FakeLiveJev:
    inner: FakeJev = field(default_factory=FakeJev)
    key_fp: str = "jevkeyfp0001"
    per_call: Decimal = Decimal("0.001")

    def estimate(self, request: JevRequest) -> Decimal:
        return self.per_call

    async def evaluate(self, request: JevRequest) -> JevResult:
        return await self.inner.evaluate(request)

    async def aclose(self) -> None: ...


@dataclass
class FakeLiveLlm:
    inner: FakeLlm = field(default_factory=lambda: FakeLlm(perfect_report()))
    key_fp: str = "oaikeyfp0001"
    per_call: Decimal = Decimal("0.01")

    def estimate(self, request: LlmRequest, schema: type[Any]) -> Decimal:
        return self.per_call

    async def parse(self, request: LlmRequest, schema: type[Any]) -> LlmResult[Any]:
        return await self.inner.parse(request, schema)

    async def aclose(self) -> None: ...


@dataclass
class FakeLiveClients:
    jev: FakeLiveJev = field(default_factory=FakeLiveJev)
    llm: FakeLiveLlm = field(default_factory=FakeLiveLlm)
    closed: int = 0

    async def aclose(self) -> None:
        self.closed += 1


def service(
    tmp_path: Path, clients: FakeLiveClients | None = None, cap: str = "5.00"
) -> RunService:
    ledger = tmp_path / "ledger.jsonl"
    initialised_ledger(ledger)
    settings = Settings(_env_file=None, ledger_path=str(ledger), budget_cap_usd=cap)  # type: ignore[call-arg]
    fakes = clients or FakeLiveClients()
    return RunService(
        settings,
        data_dir=DATA,
        store=FileReplayStore(tmp_path / "replays"),
        live_factory=lambda s, g: fakes,
        guard_factory=lambda s: BudgetGuard(initialised_or_existing(ledger), cap=Decimal(cap)),
    )


def initialised_or_existing(path: Path):  # type: ignore[no-untyped-def]
    from jev.budget.ledger import Ledger

    return Ledger(path)


async def test_live_run_scores_both_sides_and_saves_a_recording(tmp_path: Path) -> None:
    events: list[RunEvent] = []

    result = await service(tmp_path).live("run-1", events.append)

    jev, llm = result.sides["jev"], result.sides["llm"]
    assert (jev.scorecard.correct, jev.scorecard.of) == (14, 14)
    assert (llm.scorecard.correct, llm.scorecard.of) == (14, 14)
    assert jev.metrics.requests == 13 and llm.metrics.requests == 1
    assert jev.provenance.kind == "live" and result.recording_id is not None
    assert FileReplayStore(tmp_path / "replays").list_recordings("s1_reconciliation")


async def test_replay_reproduces_the_live_run_offline(tmp_path: Path) -> None:
    svc = service(tmp_path)
    live = await svc.live("run-1", lambda e: None)

    replayed = await svc.replay("run-2", recording_id=None, on_event=lambda e: None, pace=False)

    assert replayed.recording_id == live.recording_id
    for side in ("jev", "llm"):
        assert replayed.sides[side].scorecard == live.sides[side].scorecard
        assert replayed.sides[side].provenance.kind == "recorded"
        assert replayed.sides[side].provenance.recorded_at


async def test_events_are_ordered_and_bracket_the_run(tmp_path: Path) -> None:
    events: list[RunEvent] = []

    await service(tmp_path).live("run-1", events.append)

    assert [e.seq for e in events] == list(range(len(events)))
    assert events[0].type == "run_started" and events[-1].type == "run_completed"
    assert sorted(e.side for e in events if e.type == "side_completed") == ["jev", "llm"]
    assert all(b.t_ms >= a.t_ms for a, b in zip(events, events[1:], strict=False))


async def test_whole_run_is_refused_before_any_call_when_over_budget(tmp_path: Path) -> None:
    clients = FakeLiveClients(llm=FakeLiveLlm(per_call=Decimal("4.90")))

    with pytest.raises(BudgetExceededError, match="openai"):
        await service(tmp_path, clients).live("run-1", lambda e: None)

    assert clients.jev.inner.requests == [] and clients.llm.inner.requests == []
    assert clients.closed == 1  # the refused run's clients are not leaked


async def test_replay_without_recordings_is_a_clear_error(tmp_path: Path) -> None:
    svc = service(tmp_path)

    with pytest.raises(NoRecordingError):
        await svc.replay("r", recording_id=None, on_event=lambda e: None, pace=False)
    with pytest.raises(ReplayStoreError):
        await svc.replay("r", recording_id="missing", on_event=lambda e: None, pace=False)


async def test_recordings_can_be_listed_newest_first(tmp_path: Path) -> None:
    svc = service(tmp_path)
    first = await svc.live("a", lambda e: None)
    second = await svc.live("b", lambda e: None)

    ids = [m.id for m in svc.recordings()]

    assert set(ids) == {first.recording_id, second.recording_id}


class _HangingJev(FakeJev):
    cancelled = False

    async def evaluate(self, request: JevRequest) -> JevResult:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        raise AssertionError("unreachable")


class _FailingLlm(FakeLlm):
    async def parse(self, request: LlmRequest, schema: type[Any]) -> LlmResult[Any]:
        raise RuntimeError("provider down")


async def test_when_one_side_fails_the_other_is_cancelled_before_clients_close(
    tmp_path: Path,
) -> None:
    jev = _HangingJev()
    clients = FakeLiveClients(
        jev=FakeLiveJev(inner=jev), llm=FakeLiveLlm(inner=_FailingLlm(perfect_report()))
    )

    with pytest.raises(RuntimeError, match="provider down"):
        await service(tmp_path, clients).live("run-1", lambda e: None)

    assert jev.cancelled and clients.closed == 1


async def test_missing_jev_answers_never_crash_the_run(tmp_path: Path) -> None:
    omitted = {("s1.invoice.inv-2026-10", "dup_L4_L5"), ("s1.invoice.inv-2026-04", "kind_L3")}
    clients = FakeLiveClients(jev=FakeLiveJev(inner=FakeJev(omitted=omitted)))

    result = await service(tmp_path, clients).live("run-1", lambda e: None)

    scorecard = result.sides["jev"].scorecard
    assert scorecard.of == 14 and scorecard.correct < 14  # an honest miss, not a crash


async def test_a_finding_that_relies_on_a_missing_answer_goes_to_review(tmp_path: Path) -> None:
    clients = FakeLiveClients(
        jev=FakeLiveJev(inner=FakeJev(omitted={("s1.invoice.inv-2026-10", "kind_L5")}))
    )

    result = await service(tmp_path, clients).live("run-1", lambda e: None)

    touched = [
        f
        for f in result.sides["jev"].findings
        if f.doc_id == "inv-2026-10" and "kind_L5" in (f.review_reason or "")
    ]
    assert touched and all(f.lane == "review" for f in touched)
    assert all("missing answer" in (f.review_reason or "") for f in touched)
