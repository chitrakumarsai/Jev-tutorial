"""The scorecard every scenario returns, so the API and UI need no per-scenario shapes.

Policy fixed before any run (PLAN §7): a correct finding in the review lane is reported
separately, never as auto-correct. Each scenario's scorer decides what "correct" means."""

from collections.abc import Callable, Sequence
from decimal import Decimal, InvalidOperation
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, computed_field, model_validator

from jev.domain.findings import Finding

# wrong_value: the right item, but a wrong amount (S1), risk level or verdict (S2, S3)
ItemStatus = Literal["correct", "correct_in_review", "wrong_value", "missed"]
SummaryKind = Literal["count", "money", "text"]


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class ScoreItem(_Frozen):
    key_id: str
    status: ItemStatus
    finding_id: str | None
    label: str | None = None  # display name for the key item, e.g. "Breach notification"


class SummaryRow(_Frozen):
    """A scenario-specific results row. The UI formats `value` by `kind` and shows `note`
    after it; it never computes anything from it. Both sides of a run must use the same
    labels: the UI lines their rows up by label, in the first side's order."""

    label: str
    kind: SummaryKind
    value: str | None  # a count, a Decimal string, or text; None when not reported
    note: str | None = None
    ok: bool | None = None  # None: neither good nor bad

    @model_validator(mode="after")
    def _value_suits_kind(self) -> Self:
        if self.value is None or self.kind == "text":
            return self
        if self.kind == "count" and not (self.value.isascii() and self.value.isdigit()):
            raise ValueError(f"A count summary value must be digits, got {self.value!r}")
        if self.kind == "money":
            try:
                Decimal(self.value)
            except InvalidOperation:
                raise ValueError(
                    f"A money summary value must be a Decimal string, got {self.value!r}"
                ) from None
        return self


class VarianceTotal(_Frozen):
    """S1's total variance against the answer key's."""

    expected: Decimal
    reported: Decimal | None  # None when any finding left its variance out

    @computed_field  # type: ignore[prop-decorator]
    @property
    def exact(self) -> bool:
        return self.reported == self.expected


class Scorecard(_Frozen):
    items: tuple[ScoreItem, ...]
    false_positives: tuple[str, ...]
    trap_hits: tuple[str, ...]  # false positives on something planted to look wrong
    summary: tuple[SummaryRow, ...]  # required: every scorer says what its own rows are
    variance: VarianceTotal | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def of(self) -> int:
        return len(self.items)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def correct(self) -> int:
        return sum(item.status == "correct" for item in self.items)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def correct_in_review(self) -> int:
        return sum(item.status == "correct_in_review" for item in self.items)


# One side's findings -> its scorecard, with the scenario's answer key already bound.
Scorer = Callable[[Sequence[Finding]], Scorecard]
