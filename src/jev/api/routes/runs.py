"""Start runs (live or replay), read results, and stream events (SSE)."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from jev.api.deps import get_runs, get_service, get_settings
from jev.api.errors import ApiError
from jev.api.schemas import Envelope
from jev.config import Settings
from jev.replay.models import ID_PATTERN
from jev.runs.events import RunEvent
from jev.runs.service import NoRecordingError, RunService
from jev.runs.store import RunState, RunStore
from jev.scenarios.s1_reconciliation.documents import SCENARIO_ID

router = APIRouter(prefix="/api/runs", tags=["runs"])


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    mode: Literal["live", "replay"]
    recording_id: str | None = Field(default=None, pattern=ID_PATTERN)
    pace: bool = True  # replay at the recorded speed (for the animation)


def _state(runs: RunStore, run_id: str) -> RunState:
    state = runs.get(run_id)
    if state is None:
        raise ApiError(404, "UNKNOWN_RUN", f"Unknown run {run_id!r}")
    return state


@router.post("", status_code=202)
async def start_run(
    body: RunRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    service: Annotated[RunService, Depends(get_service)],
    runs: Annotated[RunStore, Depends(get_runs)],
) -> Envelope[dict[str, str]]:
    if body.scenario_id != SCENARIO_ID:
        raise ApiError(404, "UNKNOWN_SCENARIO", f"Unknown scenario {body.scenario_id!r}")
    run_id = runs.new_id()
    if body.mode == "live":
        if not settings.live_enabled:
            raise ApiError(
                403, "LIVE_DISABLED", "Live mode is off (LIVE_ENABLED=false). Use Replay."
            )
        if not runs.try_claim_live():  # claimed before the await below, so no race
            raise ApiError(409, "RUN_IN_PROGRESS", "A live run is already in progress.")
        try:
            prepared = await asyncio.to_thread(service.prepare_live, run_id)  # may refuse
        except BaseException:
            runs.release_live()
            raise
        runs.start(run_id, "live", lambda on_event: service.run_prepared(prepared, on_event))
    else:
        recording_id = body.recording_id or _newest_recording(service)
        runs.start(
            run_id,
            "replay",
            lambda on_event: service.replay(
                run_id, recording_id=recording_id, on_event=on_event, pace=body.pace
            ),
        )
    return Envelope.ok({"run_id": run_id})


def _newest_recording(service: RunService) -> str:
    metas = service.recordings()
    if not metas:
        raise NoRecordingError("No recordings yet; record a live run first.")
    return metas[0].id


@router.get("/{run_id}")
def get_run(run_id: str, runs: Annotated[RunStore, Depends(get_runs)]) -> Envelope[dict[str, Any]]:
    state = _state(runs, run_id)
    return Envelope.ok(
        {
            "run_id": state.run_id,
            "mode": state.mode,
            "status": state.status,
            "error": state.error,
            "result": state.result.model_dump(mode="json") if state.result else None,
        }
    )


def _sse(event: RunEvent) -> str:
    payload = json.dumps(event.model_dump(mode="json"))
    return f"id: {event.seq}\nevent: {event.type}\ndata: {payload}\n\n"


@router.get("/{run_id}/events")
async def events(run_id: str, runs: Annotated[RunStore, Depends(get_runs)]) -> StreamingResponse:
    state = _state(runs, run_id)

    async def stream() -> AsyncIterator[str]:
        history, queue = state.subscribe()
        try:
            for past in history:
                yield _sse(past)
            while (latest := await queue.get()) is not None:
                yield _sse(latest)
        finally:
            state.unsubscribe(queue)

    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(stream(), media_type="text/event-stream", headers=headers)
