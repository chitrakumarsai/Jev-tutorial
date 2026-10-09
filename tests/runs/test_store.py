"""Run registry: failures are reported as events, late subscribers get the full history."""

import asyncio

import pytest

from jev.runs.events import RunEvent
from jev.runs.store import RunStore


async def test_failed_run_publishes_an_error_and_is_marked_failed() -> None:
    store = RunStore()

    async def boom(on_event):  # type: ignore[no-untyped-def]
        on_event(RunEvent(seq=0, t_ms=0, type="run_started", data={}))
        raise RuntimeError("provider exploded")

    state = store.start("r1", "replay", boom)
    await asyncio.sleep(0.01)

    assert state.status == "failed"
    assert state.error == {"code": "RUN_FAILED", "message": "The run failed (RuntimeError)."}
    assert [e.type for e in state.events] == ["run_started", "run_failed"]


async def test_subscribing_after_completion_gets_history_then_end() -> None:
    store = RunStore()

    async def quick(on_event):  # type: ignore[no-untyped-def]
        on_event(RunEvent(seq=0, t_ms=0, type="run_started", data={}))
        return None

    state = store.start("r2", "live", quick)
    await asyncio.sleep(0.01)
    history, queue = state.subscribe()

    assert [e.type for e in history] == ["run_started"]
    assert await queue.get() is None
    state.unsubscribe(queue)
    state.unsubscribe(queue)  # idempotent


async def test_only_running_live_runs_block_new_live_runs() -> None:
    store = RunStore()
    gate = asyncio.Event()

    async def slow(on_event):  # type: ignore[no-untyped-def]
        await gate.wait()

    store.start("r3", "live", slow)
    assert store.live_in_progress()
    gate.set()
    await asyncio.sleep(0.01)
    assert not store.live_in_progress()


@pytest.mark.parametrize("started", [True, False])
async def test_a_cancelled_run_is_marked_failed_and_ends_subscribers(started: bool) -> None:
    store = RunStore()

    async def forever(on_event):  # type: ignore[no-untyped-def]
        await asyncio.Event().wait()

    state = store.start("r4", "live", forever)
    _, queue = state.subscribe()
    assert state._task is not None
    if started:
        await asyncio.sleep(0)  # let the run begin before cancelling it
    state._task.cancel()
    await asyncio.sleep(0.01)

    assert state.status == "failed" and not store.live_in_progress()
    assert await queue.get() is not None  # the error event
    assert await queue.get() is None


def test_a_live_claim_blocks_a_second_claim_until_released() -> None:
    store = RunStore()

    assert store.try_claim_live()
    assert store.live_in_progress() and not store.try_claim_live()
    store.release_live()
    assert store.try_claim_live()


async def test_starting_the_claimed_live_run_hands_the_claim_to_it() -> None:
    store = RunStore()
    gate = asyncio.Event()

    async def slow(on_event):  # type: ignore[no-untyped-def]
        await gate.wait()

    assert store.try_claim_live()
    store.start("r5", "live", slow)
    gate.set()
    await asyncio.sleep(0.01)

    assert not store.live_in_progress() and store.try_claim_live()


async def test_old_finished_runs_are_evicted_but_running_ones_are_kept() -> None:
    store = RunStore(keep_finished=2)
    gate = asyncio.Event()

    async def quick(on_event):  # type: ignore[no-untyped-def]
        return None

    async def slow(on_event):  # type: ignore[no-untyped-def]
        await gate.wait()

    store.start("running", "replay", slow)
    for n in range(4):
        store.start(f"done-{n}", "replay", quick)
        await asyncio.sleep(0.01)
    store.start("trigger", "replay", quick)

    assert store.get("running") is not None
    assert [r for r in ("done-0", "done-1", "done-2", "done-3") if store.get(r)] == [
        "done-2",
        "done-3",
    ]
    gate.set()
