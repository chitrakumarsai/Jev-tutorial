"""Scenario catalogue, documents (for click-to-source), recordings, and the LLM prompt."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from jev.api.deps import get_service, get_settings
from jev.api.errors import ApiError
from jev.api.schemas import Envelope
from jev.config import Settings
from jev.runs.service import RunService
from jev.scenarios.s1_reconciliation.documents import SCENARIO_ID
from jev.scenarios.s1_reconciliation.llm_pipeline import INSTRUCTIONS

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
TITLE = "Contract-to-invoice reconciliation"
DESCRIPTION = "Check 12 monthly freight invoices against the Northwind Logistics agreement."


def _known(scenario_id: str) -> None:
    if scenario_id != SCENARIO_ID:
        raise ApiError(404, "UNKNOWN_SCENARIO", f"Unknown scenario {scenario_id!r}")


@router.get("")
def list_scenarios() -> Envelope[list[dict[str, str]]]:
    return Envelope.ok([{"id": SCENARIO_ID, "title": TITLE, "description": DESCRIPTION}])


@router.get("/{scenario_id}")
def scenario(
    scenario_id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> Envelope[dict[str, Any]]:
    _known(scenario_id)
    return Envelope.ok(
        {
            "id": SCENARIO_ID,
            "title": TITLE,
            "description": DESCRIPTION,
            "llm_prompt": INSTRUCTIONS,
            "models": {"jev": settings.jev_model, "llm": settings.openai_model},
            "live_enabled": settings.live_enabled,
        }
    )


@router.get("/{scenario_id}/documents")
def documents(
    scenario_id: str, service: Annotated[RunService, Depends(get_service)]
) -> Envelope[list[dict[str, str]]]:
    _known(scenario_id)
    return Envelope.ok([{"doc_id": d.doc_id, "text": d.text} for d in service.documents.documents])


@router.get("/{scenario_id}/recordings")
def recordings(
    scenario_id: str, service: Annotated[RunService, Depends(get_service)]
) -> Envelope[list[dict[str, Any]]]:
    _known(scenario_id)
    return Envelope.ok([m.model_dump(mode="json") for m in service.recordings()])
