"""In-memory run registry (single presenter, single process). Each SSE subscriber gets its own
queue; events are also kept so late subscribers receive the full history."""

import asyncio
import inspect
import logging
import uuid
from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Any, Literal

from jev.runs.events import RunEvent
from jev.runs.models import Mode, RunResult

Status = Literal["running", "completed", "failed"]
log = logging.getLogger(__name__)
KEEP_FINISHED_RUNS = 20  # finished runs (events + results) kept for late readers


@dataclass
class RunState:
    run_id: str
    mode: Mode
    status: Status = "running"
    events: list[RunEvent] = field(default_factory=list)
    result: RunResult | None = None
    error: dict[str, str] | None = None
    _subscribers: list[asyncio.Queue[RunEvent | None]] = field(default_factory=list)
    _task: asyncio.Task[None] | None = None

    def publish(self, event: RunEvent) -> None:
        self.events.append(event)
        for queue in self._subscribers:
            queue.put_nowait(event)

    def subscribe(self) -> tuple[list[RunEvent], asyncio.Queue[RunEvent | None]]:
        """Atomically (no await): the history so far plus a queue for everything after it."""
        queue: asyncio.Queue[RunEvent | None] = asyncio.Queue()
        self._subscribers.append(queue)
        if self.status != "running":
            queue.put_nowait(None)
        return list(self.events), queue

    def unsubscribe(self, queue: asyncio.Queue[RunEvent | None]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def _finish(self, status: Status) -> None:
        self.status = status
        for queue in self._subscribers:
            queue.put_nowait(None)


class RunStore:
    def __init__(self, *, keep_finished: int = KEEP_FINISHED_RUNS) -> None:
        self._runs: dict[str, RunState] = {}
        self._keep_finished = keep_finished
        self._live_claimed = False  # held from the 409 check until the live run is registered

    def get(self, run_id: str) -> RunState | None:
        return self._runs.get(run_id)

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def live_in_progress(self) -> bool:
        running = any(r.mode == "live" and r.status == "running" for r in self._runs.values())
        return self._live_claimed or running

    def try_claim_live(self) -> bool:
        """Reserve the single live slot without awaiting, so two requests can't both pass."""
        if self.live_in_progress():
            return False
        self._live_claimed = True
        return True

    def release_live(self) -> None:
        self._live_claimed = False

    def start(self, run_id: str, mode: Mode, work_for: Any) -> RunState:
        """`work_for(on_event)` returns the awaitable that performs the run."""
        self._evict_finished()
        state = RunState(run_id=run_id, mode=mode)
        self._runs[run_id] = state
        if mode == "live":
            self._live_claimed = False  # the running state now holds the slot
        work = work_for(state.publish)
        state._task = asyncio.create_task(self._run(state, work))
        state._task.add_done_callback(self._fail_if_cancelled_early(state, work))
        return state

    def _evict_finished(self) -> None:
        """Drop the oldest finished runs beyond the limit; running ones are never dropped."""
        finished = [rid for rid, r in self._runs.items() if r.status != "running"]
        excess = len(finished) - self._keep_finished
        for run_id in finished[: max(excess, 0)]:
            del self._runs[run_id]

    @staticmethod
    def _fail_if_cancelled_early(state: RunState, work: Awaitable[RunResult]) -> Any:
        def callback(task: asyncio.Task[None]) -> None:
            if state.status == "running":  # cancelled before `_run` got to start
                if inspect.iscoroutine(work):
                    work.close()  # never started; close it so it isn't left un-awaited
                _fail(state, "CancelledError")

        return callback

    @staticmethod
    async def _run(state: RunState, work: Awaitable[RunResult]) -> None:
        try:
            state.result = await work
            state._finish("completed")
        except BaseException as exc:  # incl. cancellation: never leave a run "running"
            log.exception("Run %s failed", state.run_id)  # details stay server-side
            _fail(state, type(exc).__name__)
            if not isinstance(exc, Exception):
                raise


def _fail(state: RunState, exc_name: str) -> None:
    """Report a failure by exception class only: messages can carry request or document text."""
    state.error = {"code": "RUN_FAILED", "message": f"The run failed ({exc_name})."}
    seq = len(state.events)
    t_ms = state.events[-1].t_ms if state.events else 0
    state.publish(RunEvent(seq=seq, t_ms=t_ms, type="run_failed", data=state.error))
    state._finish("failed")
