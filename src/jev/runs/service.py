"""Run a scenario both ways at once, score each side, emit events, and record live runs."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from pydantic import BaseModel

from jev.budget.guard import BudgetGuard
from jev.budget.ledger import Provider
from jev.config import PROJECT_ROOT, Settings
from jev.domain.documents import DocumentSet
from jev.providers.factory import build_guard, build_live_clients
from jev.providers.jev.port import JevPort
from jev.providers.jev.types import JevRequest
from jev.providers.openai.port import LlmPort
from jev.providers.openai.types import LlmRequest
from jev.replay.clients import (
    RecordingJevClient,
    RecordingLlmClient,
    ReplayJevClient,
    ReplayLlmClient,
)
from jev.replay.models import Recording, RecordingMeta
from jev.replay.store import FileReplayStore
from jev.runs.events import OnEvent, RunEvent
from jev.runs.models import Mode, Provenance, RunResult, SideResult
from jev.scenarios.base import JevSidePipeline, LlmSidePipeline, Side, SideOutput
from jev.scenarios.registry import S1, ScenarioSpec
from jev.scoring.metrics import metrics_for

DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


class NoRecordingError(LookupError):
    """Replay was requested but nothing has been recorded for this scenario yet."""


class LiveJevLike(JevPort, Protocol):
    @property
    def key_fp(self) -> str: ...
    def estimate(self, request: JevRequest) -> Decimal: ...


class LiveLlmLike(LlmPort, Protocol):
    @property
    def key_fp(self) -> str: ...
    def estimate(self, request: LlmRequest, schema: type[BaseModel]) -> Decimal: ...


class LiveClientsLike(Protocol):
    @property
    def jev(self) -> LiveJevLike: ...
    @property
    def llm(self) -> LiveLlmLike: ...
    async def aclose(self) -> None: ...


LiveFactory = Callable[[Settings, BudgetGuard], LiveClientsLike]


class _Emitter:
    """Stamps pipeline events with a sequence number and time since the run started."""

    def __init__(self, on_event: OnEvent) -> None:
        self._on_event, self._seq, self._t0 = on_event, 0, perf_counter()

    def __call__(self, type_: str, side: Side | None, data: dict[str, Any]) -> None:
        t_ms = round((perf_counter() - self._t0) * 1000)
        event = RunEvent(seq=self._seq, t_ms=t_ms, type=type_, side=side, data=data)  # type: ignore[arg-type]
        self._seq += 1
        self._on_event(event)


ProvenanceFor = Callable[[Side, SideOutput], Provenance]


@dataclass(frozen=True)
class PreparedLive:
    run_id: str
    clients: LiveClientsLike
    jev_pipe: JevSidePipeline
    llm_pipe: LlmSidePipeline
    estimates: dict[Provider, Decimal]  # worst-case reservation per provider for this run


class RunService:
    def __init__(
        self,
        settings: Settings,
        *,
        scenario: ScenarioSpec = S1,  # a convenience for S1-only callers and tests
        data_dir: Path = DEFAULT_DATA_DIR,
        store: FileReplayStore | None = None,
        live_factory: LiveFactory = build_live_clients,
        guard_factory: Callable[[Settings], BudgetGuard] = build_guard,
    ) -> None:
        self._settings = settings
        self._scenario = scenario
        self._docs: DocumentSet = scenario.load_documents(data_dir)
        self._score = scenario.load_scorer(data_dir)
        self._store = store or FileReplayStore(data_dir / "replays")
        self._live_factory = live_factory
        self._guard_factory = guard_factory

    @property
    def scenario(self) -> ScenarioSpec:
        return self._scenario

    @property
    def documents(self) -> DocumentSet:
        return self._docs

    def recordings(self) -> list[RecordingMeta]:
        return self._store.list_recordings(self._scenario.id)

    def _pipelines(self, run_id: str) -> tuple[JevSidePipeline, LlmSidePipeline]:
        return self._scenario.build_pipelines(self._docs, self._settings, run_id)

    async def replay(
        self, run_id: str, *, recording_id: str | None, on_event: OnEvent, pace: bool = True
    ) -> RunResult:
        if recording_id is None:
            metas = self.recordings()
            if not metas:
                raise NoRecordingError(
                    f"No recordings for {self._scenario.id} yet; record a live run first."
                )
            recording_id = metas[0].id
        rec = await asyncio.to_thread(self._store.load, self._scenario.id, recording_id)

        def provenance(side: Side, output: SideOutput) -> Provenance:
            return Provenance(
                kind="recorded",
                models=output.models,
                recording_id=rec.id,
                recorded_at=rec.recorded_at,
            )

        emit = _Emitter(on_event)
        jev_pipe, llm_pipe = self._pipelines(run_id)
        sides = await self._execute(
            run_id,
            "replay",
            emit,
            provenance,
            jev_pipe.run(ReplayJevClient(rec, pace=pace), emit),
            rec.jev_model,
            llm_pipe.run(ReplayLlmClient(rec, pace=pace), emit),
            rec.llm_model,
        )
        return self._complete(emit, run_id, "replay", sides, rec.id)

    def prepare_live(self, run_id: str) -> "PreparedLive":
        """Everything that can refuse a live run, before anything is sent: live mode on, keys
        present (factory), and the whole run's worst-case cost within budget (pre-flight).
        Sync and blocking (ledger lock): call it from a thread or a sync CLI, never on a loop."""
        guard = self._guard_factory(self._settings)
        clients = self._live_factory(self._settings, guard)
        jev_pipe, llm_pipe = self._pipelines(run_id)
        try:
            jev_total = sum((clients.jev.estimate(r) for r in jev_pipe.requests()), Decimal("0"))
            llm_total = clients.llm.estimate(llm_pipe.request(), self._scenario.llm_schema)
            estimates: dict[tuple[Provider, str], Decimal] = {
                ("typesafe", clients.jev.key_fp): jev_total,
                ("openai", clients.llm.key_fp): llm_total,
            }
            guard.preflight(estimates)
        except BaseException:
            asyncio.run(clients.aclose())  # a refused run must not leak its HTTP clients
            raise
        per_provider = {provider: amount for (provider, _), amount in estimates.items()}
        return PreparedLive(run_id, clients, jev_pipe, llm_pipe, per_provider)

    async def run_prepared(
        self, prepared: "PreparedLive", on_event: OnEvent, *, record: bool = True
    ) -> RunResult:
        s, clients = self._settings, prepared.clients
        try:
            jev_rec = RecordingJevClient(clients.jev, model=s.jev_model)
            llm_rec = RecordingLlmClient(clients.llm, model=s.openai_model)
            emit = _Emitter(on_event)
            sides = await self._execute(
                prepared.run_id,
                "live",
                emit,
                lambda side, out: Provenance(kind="live", models=out.models),
                prepared.jev_pipe.run(jev_rec, emit),
                s.jev_model,
                prepared.llm_pipe.run(llm_rec, emit),
                s.openai_model,
            )
            recording_id = None
            if record:
                recording = Recording.create(
                    self._scenario.id,
                    jev_model=s.jev_model,
                    llm_model=s.openai_model,
                    calls=[*jev_rec.calls, *llm_rec.calls],
                )
                await asyncio.to_thread(self._store.save, recording)
                recording_id = recording.id
            return self._complete(emit, prepared.run_id, "live", sides, recording_id)
        finally:
            await clients.aclose()

    async def live(self, run_id: str, on_event: OnEvent, *, record: bool = True) -> RunResult:
        prepared = await asyncio.to_thread(self.prepare_live, run_id)
        return await self.run_prepared(prepared, on_event, record=record)

    async def _execute(
        self,
        run_id: str,
        mode: Mode,
        emit: _Emitter,
        provenance: ProvenanceFor,
        jev_work: Awaitable[SideOutput],
        jev_model: str,
        llm_work: Awaitable[SideOutput],
        llm_model: str,
    ) -> dict[str, SideResult]:
        emit(
            "run_started",
            None,
            {"run_id": run_id, "scenario_id": self._scenario.id, "mode": mode},
        )

        async def side(name: Side, model: str, work: Awaitable[SideOutput]) -> SideResult:
            started = perf_counter()
            output = await work
            wall_ms = round((perf_counter() - started) * 1000)
            result = SideResult(
                side=name,
                findings=output.findings,
                metrics=metrics_for(model, output.usages, wall_ms=wall_ms),
                scorecard=self._score(output.findings),
                provenance=provenance(name, output),
                notes=output.notes,
            )
            emit("side_completed", name, {"result": result.model_dump(mode="json")})
            return result

        tasks = {
            "jev": asyncio.ensure_future(side("jev", jev_model, jev_work)),
            "llm": asyncio.ensure_future(side("llm", llm_model, llm_work)),
        }
        try:
            await asyncio.gather(*tasks.values())
        except BaseException:
            # A failed side must not leave the other spending on clients about to be closed.
            for task in tasks.values():
                task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)
            raise
        return {name: task.result() for name, task in tasks.items()}

    def _complete(
        self,
        emit: _Emitter,
        run_id: str,
        mode: Mode,
        sides: dict[str, SideResult],
        recording_id: str | None,
    ) -> RunResult:
        result = RunResult(
            run_id=run_id,
            scenario_id=self._scenario.id,
            mode=mode,
            sides=sides,
            recording_id=recording_id,
        )
        emit("run_completed", None, {"result": result.model_dump(mode="json")})
        return result
