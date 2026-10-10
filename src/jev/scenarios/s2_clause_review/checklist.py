"""The fixed audit checklist S2 reviews the addendum against, written before any model run."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from jev.scenarios.s2_clause_review.documents import scenario_dir


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChecklistClause(_Frozen):
    id: str = Field(pattern=r"^[a-z_]+$")
    title: str
    look_for: str  # what counts as this clause, in plain words (the Jev question's subject)
    # Wording that would mean the clause is there; an "absent" key item must match none.
    absence_phrases: tuple[str, ...] = Field(min_length=1)
    risk_rubric: tuple[str, str, str, str]  # descriptions for low, medium, high, critical


class Checklist(_Frozen):
    scenario_id: str
    version: int
    clauses: tuple[ChecklistClause, ...] = Field(min_length=1)


def load_checklist(data_dir: Path) -> Checklist:
    path = scenario_dir(data_dir) / "checklist.json"
    return Checklist.model_validate_json(path.read_text(encoding="utf-8"))
