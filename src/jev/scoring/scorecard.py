"""Score one side's findings against the answer key. Policy fixed before any run (PLAN §7):
a correct finding in the review lane is reported separately, never as auto-correct."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from jev.domain.findings import Finding
from jev.scoring.answer_key import AnswerKey, KeyItem

ItemStatus = Literal["correct", "correct_in_review", "wrong_amount", "missed"]


class ScoreItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    key_id: str
    status: ItemStatus
    finding_id: str | None


class Scorecard(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[ScoreItem, ...]
    false_positives: tuple[str, ...]
    trap_hits: tuple[str, ...]
    total_variance_expected: Decimal
    total_variance_reported: Decimal | None

    @property
    def of(self) -> int:
        return len(self.items)

    @property
    def correct(self) -> int:
        return sum(item.status == "correct" for item in self.items)

    @property
    def correct_in_review(self) -> int:
        return sum(item.status == "correct_in_review" for item in self.items)

    @property
    def total_variance_exact(self) -> bool:
        return self.total_variance_reported == self.total_variance_expected


def _status(item: KeyItem, finding: Finding | None) -> ItemStatus:
    if finding is None:
        return "missed"
    if finding.variance != item.variance:
        return "wrong_amount"
    return "correct_in_review" if finding.lane == "review" else "correct"


def _best_match(item: KeyItem, candidates: Sequence[Finding]) -> Finding | None:
    """Order-independent: prefer the same line and amount, then the same line, then the amount."""
    same = [f for f in candidates if (f.doc_id, f.kind) == (item.doc_id, item.kind)]
    preferences = (
        lambda f: f.line_ref == item.line_ref and f.variance == item.variance,
        lambda f: f.line_ref == item.line_ref,
        lambda f: f.variance == item.variance,
        lambda f: True,
    )
    for prefers in preferences:
        match = next((f for f in same if prefers(f)), None)
        if match is not None:
            return match
    return None


def score(findings: Sequence[Finding], key: AnswerKey) -> Scorecard:
    unused = list(findings)
    items: list[ScoreItem] = []
    for item in key.items:
        match = _best_match(item, unused)
        if match is not None:
            unused.remove(match)
        items.append(
            ScoreItem(
                key_id=item.id, status=_status(item, match), finding_id=match.id if match else None
            )
        )

    traps = {(n.doc_id, n.line_ref) for n in key.non_issues}
    variances = [f.variance for f in findings]
    reported = (
        None
        if any(v is None for v in variances)
        else sum((v for v in variances if v is not None), Decimal("0"))
    )
    return Scorecard(
        items=tuple(items),
        false_positives=tuple(f.id for f in unused),
        trap_hits=tuple(f.id for f in unused if (f.doc_id, f.line_ref) in traps),
        total_variance_expected=key.total_variance,
        total_variance_reported=reported,
    )
