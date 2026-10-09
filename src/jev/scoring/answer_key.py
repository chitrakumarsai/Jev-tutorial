"""Answer-key model. Keys are written by hand before any model run and validated on load."""

from decimal import Decimal
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

FindingKind = Literal[
    "discount_not_applied",
    "surcharge_on_undiscounted_base",
    "surcharge_over_cap",
    "duplicate_line",
    "late_fee_incorrect",
    "rate_mismatch",
]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Evidence(_Frozen):
    doc_id: str
    quote: str = Field(min_length=1)


class KeyItem(_Frozen):
    """One expected finding: what was billed, what should have been billed, and why."""

    id: str
    kind: FindingKind
    doc_id: str
    line_ref: str
    billed: Decimal
    expected: Decimal
    variance: Decimal
    evidence: tuple[Evidence, ...]

    @model_validator(mode="after")
    def _variance_matches(self) -> Self:
        if self.billed - self.expected != self.variance:
            raise ValueError(f"{self.id}: variance must equal billed - expected")
        return self


class NonIssue(_Frozen):
    """Something that looks wrong but is allowed; reporting it is a false positive."""

    doc_id: str
    line_ref: str
    note: str


class AnswerKey(_Frozen):
    scenario_id: str
    version: int
    authored_at: str
    contract_terms: dict[str, str | int]
    cumulative_loads_by_month: dict[str, int]
    items: tuple[KeyItem, ...]
    clean_invoices: tuple[str, ...]
    non_issues: tuple[NonIssue, ...]
    total_variance: Decimal

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [item.id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("answer-key item ids must be unique")
        total = sum((item.variance for item in self.items), Decimal("0"))
        if total != self.total_variance:
            raise ValueError(f"total_variance {self.total_variance} != sum of items {total}")
        return self


def load_answer_key(path: Path) -> AnswerKey:
    """Load and validate an answer key; raises FileNotFoundError or ValidationError."""
    return AnswerKey.model_validate_json(path.read_text(encoding="utf-8"))
