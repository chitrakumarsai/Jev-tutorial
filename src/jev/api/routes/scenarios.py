"""Scenario catalogue, documents (for click-to-source), recordings, and the LLM prompt."""

from collections.abc import Mapping
from typing import Annotated

from fastapi import APIRouter, Depends

from jev.api.deps import get_services, get_settings, service_for
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

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])
Services = Annotated[Mapping[str, RunService], Depends(get_services)]


def _summary(service: RunService) -> ScenarioSummary:
    spec = service.scenario
    return ScenarioSummary(id=spec.id, title=spec.title, description=spec.description)


@router.get("", summary="List scenarios")
def list_scenarios(services: Services) -> Envelope[list[ScenarioSummary]]:
    return Envelope.ok([_summary(service) for service in services.values()])


@router.get("/{scenario_id}", summary="Scenario detail", responses=error_responses(404))
def scenario(
    scenario_id: str, settings: Annotated[Settings, Depends(get_settings)], services: Services
) -> Envelope[ScenarioDetail]:
    service = service_for(services, scenario_id)
    return Envelope.ok(
        ScenarioDetail(
            **_summary(service).model_dump(),
            llm_prompt=service.scenario.llm_instructions,
            models=ModelNames(jev=settings.jev_model, llm=settings.openai_model),
            live_enabled=settings.live_enabled,
        )
    )


@router.get("/{scenario_id}/documents", summary="Document text", responses=error_responses(404))
def documents(scenario_id: str, services: Services) -> Envelope[list[DocumentText]]:
    docs = service_for(services, scenario_id).documents.documents
    return Envelope.ok([DocumentText(doc_id=d.doc_id, text=d.text) for d in docs])


@router.get(
    "/{scenario_id}/recordings",
    summary="Recordings available for replay, newest first",
    responses=error_responses(404, 500),
)
def recordings(scenario_id: str, services: Services) -> Envelope[list[RecordingMeta]]:
    return Envelope.ok(service_for(services, scenario_id).recordings())
