"""S2 answer key: per checklist clause, whether it is present, where, and how risky."""

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jev.domain.findings import ClauseVerdict, Risk
from jev.scenarios.s2_clause_review.documents import scenario_dir


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class S2KeyItem(_Frozen):
    id: str
    clause_id: str
    status: ClauseVerdict
    first_line: int | None = Field(default=None, ge=1)  # 1-based lines of the addendum
    last_line: int | None = Field(default=None, ge=1)
    quote: str | None = None  # verbatim, on one line, inside first_line..last_line
    risk: Risk | None = None
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def _fits_status(self) -> Self:
        located = (self.first_line, self.last_line, self.quote, self.risk)
        if self.status == "absent":
            if any(value is not None for value in located):
                raise ValueError(f"{self.id}: an absent clause has no lines, quote or risk")
            return self
        if any(value is None for value in located):
            raise ValueError(f"{self.id}: a {self.status} clause needs lines, a quote and a risk")
        if self.first_line > self.last_line:  # type: ignore[operator]
            raise ValueError(f"{self.id}: first_line is after last_line")
        return self


class S2Key(_Frozen):
    scenario_id: str
    version: int
    authored_at: str
    line_numbering: str
    items: tuple[S2KeyItem, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        for field in ("id", "clause_id"):
            values = [getattr(item, field) for item in self.items]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {field} in the S2 answer key")
        return self


def load_s2_key(data_dir: Path) -> S2Key:
    path = scenario_dir(data_dir) / "answer_key.json"
    return S2Key.model_validate_json(path.read_text(encoding="utf-8"))
