"""Score S1 findings against the hand-written answer key: exact Decimal variances."""

from collections.abc import Sequence
from decimal import Decimal
from functools import partial
from pathlib import Path

from jev.domain.findings import Finding
from jev.domain.money import decimal_str
from jev.scenarios.s1_reconciliation.documents import scenario_dir
from jev.scoring.answer_key import AnswerKey, KeyItem, load_answer_key
from jev.scoring.scorecard import (
    ItemStatus,
    Scorecard,
    ScoreItem,
    Scorer,
    SummaryRow,
    VarianceTotal,
)


def _status(item: KeyItem, finding: Finding | None) -> ItemStatus:
    if finding is None:
        return "missed"
    if finding.variance != item.variance:
        return "wrong_value"
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


def _reported_total(findings: Sequence[Finding]) -> Decimal | None:
    variances = [f.variance for f in findings]
    if any(v is None for v in variances):
        return None
    return sum((v for v in variances if v is not None), Decimal("0"))


def _summary(items: Sequence[ScoreItem], variance: VarianceTotal) -> tuple[SummaryRow, ...]:
    wrong = sum(item.status == "wrong_value" for item in items)
    reported = variance.reported
    return (
        SummaryRow(label="Wrong amounts", kind="count", value=str(wrong), ok=wrong == 0),
        SummaryRow(
            label="Total variance",
            kind="money",
            value=None if reported is None else decimal_str(reported),
            note="Not reported" if reported is None else ("exact" if variance.exact else None),
            ok=variance.exact,
        ),
    )


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
    variance = VarianceTotal(expected=key.total_variance, reported=_reported_total(findings))
    return Scorecard(
        items=tuple(items),
        false_positives=tuple(f.id for f in unused),
        trap_hits=tuple(f.id for f in unused if (f.doc_id, f.line_ref) in traps),
        summary=_summary(items, variance),
        variance=variance,
    )


def load_s1_scorer(data_dir: Path) -> Scorer:
    key = load_answer_key(scenario_dir(data_dir) / "answer_key.json")
    return partial(score, key=key)
