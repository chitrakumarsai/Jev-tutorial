"""Typed response payloads, so the OpenAPI spec (and the generated web client) is precise.
Money stays a string end to end; the UI never does maths."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from jev.api.schemas import ApiError, Envelope
from jev.runs.models import Mode, RunResult
from jev.runs.store import Status


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ScenarioSummary(_Frozen):
    id: str
    title: str
    description: str


class ModelNames(_Frozen):
    jev: str
    llm: str


class ScenarioDetail(ScenarioSummary):
    llm_prompt: str
    models: ModelNames
    live_enabled: bool


class DocumentText(_Frozen):
    doc_id: str
    text: str


class RunStarted(_Frozen):
    run_id: str


class RunStatus(_Frozen):
    run_id: str
    mode: Mode
    status: Status
    error: ApiError | None
    result: RunResult | None


class BudgetRow(_Frozen):
    provider: str
    cap: str
    key_configured: bool
    spent: str | None
    reserved: str | None
    remaining: str | None


class BudgetReport(_Frozen):
    ledger_initialised: bool
    providers: list[BudgetRow]


def error_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Declare failures as the envelope (incl. 422, replacing FastAPI's default schema)."""
    return {
        status: {"model": Envelope[None], "description": "Failure envelope"}
        for status in (*statuses, 422)
    }
