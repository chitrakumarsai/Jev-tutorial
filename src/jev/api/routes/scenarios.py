"""Scenario catalogue, documents (for click-to-source), recordings, and the LLM prompt."""

from typing import Annotated

from fastapi import APIRouter, Depends

from jev.api.deps import get_service, get_settings
from jev.api.errors import ApiError
from jev.api.models import (
    DocumentText,
    ModelNames,
    ScenarioDetail,
    ScenarioSummary,
    error_responses,
)
from jev.api.schemas import Envelope
from jev.config import Settings
from jev.replay.models import RecordingMeta
from jev.runs.service import RunService
from jev.scenarios.s1_reconciliation.documents import SCENARIO_ID
from jev.scenarios.s1_reconciliation.llm_pipeline import INSTRUCTIONS

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
TITLE = "Contract-to-invoice reconciliation"
DESCRIPTION = "Check 12 monthly freight invoices against the Northwind Logistics agreement."


def _known(scenario_id: str) -> None:
    if scenario_id != SCENARIO_ID:
        raise ApiError(404, "UNKNOWN_SCENARIO", f"Unknown scenario {scenario_id!r}")


SUMMARY = ScenarioSummary(id=SCENARIO_ID, title=TITLE, description=DESCRIPTION)


@router.get("", summary="List scenarios")
def list_scenarios() -> Envelope[list[ScenarioSummary]]:
    return Envelope.ok([SUMMARY])


@router.get("/{scenario_id}", summary="Scenario detail", responses=error_responses(404))
def scenario(
    scenario_id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> Envelope[ScenarioDetail]:
    _known(scenario_id)
    return Envelope.ok(
        ScenarioDetail(
            **SUMMARY.model_dump(),
            llm_prompt=INSTRUCTIONS,
            models=ModelNames(jev=settings.jev_model, llm=settings.openai_model),
            live_enabled=settings.live_enabled,
        )
    )


@router.get("/{scenario_id}/documents", summary="Document text", responses=error_responses(404))
def documents(
    scenario_id: str, service: Annotated[RunService, Depends(get_service)]
) -> Envelope[list[DocumentText]]:
    _known(scenario_id)
    docs = service.documents.documents
    return Envelope.ok([DocumentText(doc_id=d.doc_id, text=d.text) for d in docs])


@router.get(
    "/{scenario_id}/recordings",
    summary="Recordings available for replay, newest first",
    responses=error_responses(404, 500),
)
def recordings(
    scenario_id: str, service: Annotated[RunService, Depends(get_service)]
) -> Envelope[list[RecordingMeta]]:
    _known(scenario_id)
    return Envelope.ok(service.recordings())
