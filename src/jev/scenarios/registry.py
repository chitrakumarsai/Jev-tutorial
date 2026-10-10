"""Every scenario the app can run, looked up by id. Add a scenario by adding a spec here."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from jev.config import Settings
from jev.domain.documents import DocumentSet
from jev.replay.models import ID_PATTERN
from jev.scenarios.base import JevSidePipeline, LlmSidePipeline
from jev.scenarios.s1_reconciliation import documents as s1_documents
from jev.scenarios.s1_reconciliation.jev_pipeline import JevS1Pipeline
from jev.scenarios.s1_reconciliation.llm_pipeline import INSTRUCTIONS as S1_INSTRUCTIONS
from jev.scenarios.s1_reconciliation.llm_pipeline import LlmS1Pipeline
from jev.scenarios.s1_reconciliation.llm_schema import S1LlmReport
from jev.scenarios.s1_reconciliation.scorer import load_s1_scorer
from jev.scoring.scorecard import Scorer

# (documents, settings, run id) -> the two sides of one run
PipelineFactory = Callable[[DocumentSet, Settings, str], tuple[JevSidePipeline, LlmSidePipeline]]


@dataclass(frozen=True)
class ScenarioSpec:
    """What the run service, API and CLI need to know about one scenario."""

    id: str  # also the folder name under data/replays/, so it must match ID_PATTERN
    alias: str  # short name for the CLI, e.g. "s1"
    title: str
    description: str
    llm_instructions: str  # shown in the UI word for word, for fairness
    llm_schema: type[BaseModel]
    load_documents: Callable[[Path], DocumentSet]  # data_dir -> documents
    load_scorer: Callable[[Path], Scorer]  # data_dir -> scorer bound to the hand-written key
    build_pipelines: PipelineFactory
    validate_data: Callable[[Path], list[str]]  # data_dir -> problems ([] when consistent)

    def __post_init__(self) -> None:
        for name in (self.id, self.alias):
            if not re.fullmatch(ID_PATTERN, name):
                raise ValueError(f"Scenario id or alias {name!r} must match {ID_PATTERN}")


def _s1_pipelines(
    docs: DocumentSet, settings: Settings, run_id: str
) -> tuple[JevSidePipeline, LlmSidePipeline]:
    return (
        JevS1Pipeline(docs, review_threshold=settings.review_threshold, run_id=run_id),
        LlmS1Pipeline(docs, run_id=run_id),
    )


S1 = ScenarioSpec(
    id=s1_documents.SCENARIO_ID,
    alias="s1",
    title="Contract-to-invoice reconciliation",
    description="Check 12 monthly freight invoices against the Northwind Logistics agreement.",
    llm_instructions=S1_INSTRUCTIONS,
    llm_schema=S1LlmReport,
    load_documents=s1_documents.load_s1_documents,
    load_scorer=load_s1_scorer,
    build_pipelines=_s1_pipelines,
    validate_data=s1_documents.validate_s1_data,
)

SCENARIOS: tuple[ScenarioSpec, ...] = (S1,)


def get_scenario(name: str) -> ScenarioSpec | None:
    """A scenario by full id or alias."""
    return next((spec for spec in SCENARIOS if name in (spec.id, spec.alias)), None)
