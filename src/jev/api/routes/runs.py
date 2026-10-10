"""Start runs (live or replay), read results, and stream events (SSE)."""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from jev.api.deps import get_runs, get_services, get_settings, service_for
from jev.api.errors import ApiError
from jev.api.models import RunStarted, RunStatus, error_responses
from jev.api.schemas import ApiError as ErrorBody
from jev.api.schemas import Envelope
from jev.config import Settings
from jev.replay.models import ID_PATTERN
from jev.runs.events import RunEvent
from jev.runs.service import NoRecordingError, RunService
from jev.runs.store import RunState, RunStore

router = APIRouter(prefix="/api/runs", tags=["runs"])
KEEPALIVE_S = 15.0  # comment lines keep idle streams open through proxies


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


@router.post(
    "",
    status_code=202,
    summary="Start a live or replay run",
    responses=error_responses(403, 404, 409),
)
async def start_run(
    body: RunRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    services: Annotated[Mapping[str, RunService], Depends(get_services)],
    runs: Annotated[RunStore, Depends(get_runs)],
) -> Envelope[RunStarted]:
    service = service_for(services, body.scenario_id)
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
        recording_id = await asyncio.to_thread(_recording_to_replay, service, body.recording_id)
        runs.start(
            run_id,
            "replay",
            lambda on_event: service.replay(
                run_id, recording_id=recording_id, on_event=on_event, pace=body.pace
            ),
        )
    return Envelope.ok(RunStarted(run_id=run_id))


def _recording_to_replay(service: RunService, requested: str | None) -> str:
    """Resolve before starting, so a missing recording is a 404, not a failed run."""
    ids = [meta.id for meta in service.recordings()]
    if requested is None:
        if not ids:
            raise NoRecordingError("No recordings yet; record a live run first.")
        return ids[0]
    if requested not in ids:
        raise NoRecordingError(f"No recording {requested!r} for {service.scenario.id}.")
    return requested


@router.get("/{run_id}", summary="Run status and result", responses=error_responses(404))
def get_run(run_id: str, runs: Annotated[RunStore, Depends(get_runs)]) -> Envelope[RunStatus]:
    state = _state(runs, run_id)
    return Envelope.ok(
        RunStatus(
            run_id=state.run_id,
            mode=state.mode,
            status=state.status,
            error=ErrorBody(**state.error) if state.error else None,
            result=state.result,
        )
    )


def _sse(event: RunEvent) -> str:
    payload = json.dumps(event.model_dump(mode="json"))
    return f"id: {event.seq}\nevent: {event.type}\ndata: {payload}\n\n"


async def event_stream(
    state: RunState, *, after: int, keepalive_s: float = KEEPALIVE_S
) -> AsyncIterator[str]:
    """History (minus events up to `after`), then live events; ends after the final event."""
    history, queue = state.subscribe()
    try:
        for past in history:
            if past.seq > after:
                yield _sse(past)
        while True:
            try:
                latest = await asyncio.wait_for(queue.get(), timeout=keepalive_s)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            if latest is None:
                return
            if latest.seq > after:
                yield _sse(latest)
    finally:
        state.unsubscribe(queue)


SSE_DOC = (
    "Server-sent events: `id` is the event seq, `event` its type (run_started, step, finding, "
    "side_completed, run_completed, run_failed), `data` the RunEvent JSON. Send Last-Event-ID "
    "to resume. The stream closes after run_completed or run_failed; clients should close too."
)


@router.get(
    "/{run_id}/events",
    summary="Stream run events (SSE)",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": SSE_DOC},
        204: {"description": "Run finished and every event was already seen"},
        **error_responses(404),
    },
)
async def events(
    run_id: str,
    runs: Annotated[RunStore, Depends(get_runs)],
    last_event_id: Annotated[int | None, Header()] = None,
) -> Response:
    state = _state(runs, run_id)
    after = -1 if last_event_id is None else last_event_id
    if state.status != "running" and state.events and after >= state.events[-1].seq:
        return Response(status_code=204)  # fully seen: 204 stops EventSource reconnecting
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(
        event_stream(state, after=after), media_type="text/event-stream", headers=headers
    )
