"""Score S2 findings against the hand-written key: per checklist clause, the verdict, where it
is (when present or partial), its risk level, and that any quoted evidence was found."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path

from jev.domain.findings import Finding
from jev.scenarios.s2_clause_review.answer_key import S2Key, S2KeyItem, load_s2_key
from jev.scenarios.s2_clause_review.checklist import load_checklist
from jev.scoring.scorecard import ItemStatus, Scorecard, ScoreItem, Scorer, SummaryRow

MISSING_CLAUSE = "breach_notification"  # the headline trap: the clause the addendum lacks


def _line(finding: Finding) -> int | None:
    ref = finding.line_ref or ""
    return int(ref[1:]) if ref[:1] == "L" and ref[1:].isdigit() else None


def _located(item: S2KeyItem, finding: Finding) -> bool:
    if item.status == "absent":
        return True
    line = _line(finding)
    return (
        line is not None
        and item.first_line is not None
        and item.last_line is not None
        and item.first_line <= line <= item.last_line
    )


def _status(item: S2KeyItem, finding: Finding | None) -> ItemStatus:
    if finding is None or finding.verdict is None:
        return "missed"
    right = (
        finding.verdict == item.status
        and finding.risk == item.risk
        and _located(item, finding)
        and finding.traceable
    )
    if not right:
        return "wrong_value"
    return "correct_in_review" if finding.lane == "review" else "correct"


def _summary(key: S2Key, by_clause: dict[str, Finding]) -> tuple[SummaryRow, ...]:
    judged = [
        (item, by_clause[item.clause_id]) for item in key.items if item.clause_id in by_clause
    ]
    wrong_verdicts = sum(f.verdict is not None and f.verdict != i.status for i, f in judged)
    wrong_risks = sum(f.risk is not None and f.risk != i.risk for i, f in judged)
    missing = by_clause.get(MISSING_CLAUSE)
    caught = missing is not None and missing.verdict == "absent"
    return (
        SummaryRow(
            label="Missing clause caught", kind="text", value="Yes" if caught else "No", ok=caught
        ),
        SummaryRow(
            label="Wrong verdicts", kind="count", value=str(wrong_verdicts), ok=wrong_verdicts == 0
        ),
        SummaryRow(
            label="Wrong risk levels", kind="count", value=str(wrong_risks), ok=wrong_risks == 0
        ),
    )


def score(findings: Sequence[Finding], key: S2Key, titles: dict[str, str]) -> Scorecard:
    clauses = {item.clause_id for item in key.items}
    by_clause: dict[str, Finding] = {}
    for f in findings:
        if f.kind in clauses:
            by_clause.setdefault(f.kind, f)  # pipelines report one finding per clause
    items = tuple(
        ScoreItem(
            key_id=item.id,
            status=_status(item, by_clause.get(item.clause_id)),
            finding_id=by_clause[item.clause_id].id if item.clause_id in by_clause else None,
            label=titles.get(item.clause_id),
        )
        for item in key.items
    )
    traps = {item.id for item in key.items if item.trap}
    trap_hits = tuple(
        i.finding_id
        for i in items
        if i.key_id in traps and i.status == "wrong_value" and i.finding_id
    )
    used = {id(f) for f in by_clause.values()}
    return Scorecard(
        items=items,
        false_positives=tuple(f.id for f in findings if id(f) not in used),
        trap_hits=trap_hits,
        summary=_summary(key, by_clause),
    )


def load_s2_scorer(data_dir: Path) -> Scorer:
    titles = {clause.id: clause.title for clause in load_checklist(data_dir).clauses}
    return partial(score, key=load_s2_key(data_dir), titles=titles)
