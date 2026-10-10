"""Score S2 findings against the hand-written key: per checklist clause, the verdict, where it
is (when present or partial), its risk level, and that any quoted evidence was found."""

import re
from collections.abc import Sequence
from functools import partial
from pathlib import Path

from jev.domain.findings import Finding
from jev.scenarios.s2_clause_review.answer_key import S2Key, S2KeyItem, load_s2_key
from jev.scenarios.s2_clause_review.checklist import load_checklist
from jev.scenarios.s2_clause_review.documents import ADDENDUM_ID, load_s2_documents
from jev.scoring.scorecard import ItemStatus, Scorecard, ScoreItem, Scorer, SummaryRow

MISSING_CLAUSE = "breach_notification"  # the headline trap: the clause the addendum lacks


_LINE_REF = re.compile(r"L(\d{1,4})")


def _lines(finding: Finding, text: str) -> list[tuple[int, int]]:
    """1-based line ranges the finding points at: its evidence spans, else its line_ref.
    Jev's evidence is the one line it picked; the LLM's is its whole quote, so both sides are
    judged by the same rule: does what they point at overlap the clause?"""
    if finding.evidence:
        return [
            (
                text.count("\n", 0, span.start) + 1,
                text.count("\n", 0, max(span.end - 1, span.start)) + 1,
            )
            for span in finding.evidence
        ]
    match = _LINE_REF.fullmatch(finding.line_ref or "")
    return [(int(match[1]), int(match[1]))] if match else []


def _located(item: S2KeyItem, finding: Finding, text: str) -> bool:
    if item.status == "absent":
        return True
    first, last = item.first_line, item.last_line
    if first is None or last is None:
        return False
    return any(start <= last and end >= first for start, end in _lines(finding, text))


def _status(item: S2KeyItem, finding: Finding | None, text: str) -> ItemStatus:
    if finding is None or finding.verdict is None:
        return "missed"
    right = (
        finding.verdict == item.status
        and finding.risk == item.risk
        and _located(item, finding, text)
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
    # An answered clause with no readable risk got its risk wrong too.
    wrong_risks = sum(f.verdict is not None and f.risk != i.risk for i, f in judged)
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


def score(findings: Sequence[Finding], key: S2Key, titles: dict[str, str], text: str) -> Scorecard:
    """Findings for clauses outside the key, or repeats, are false positives."""
    clauses = {item.clause_id for item in key.items}
    by_clause: dict[str, Finding] = {}
    for f in findings:
        if f.kind in clauses:
            by_clause.setdefault(f.kind, f)  # pipelines report one finding per clause
    items = tuple(
        ScoreItem(
            key_id=item.id,
            status=_status(item, by_clause.get(item.clause_id), text),
            finding_id=by_clause[item.clause_id].id if item.clause_id in by_clause else None,
            label=titles.get(item.clause_id),
        )
        for item in key.items
    )
    # A trap is hit only by a confident (auto-lane) wrong verdict on it, not a wrong risk alone
    # and not an answer a human would catch in review.
    trap_ids = {item.clause_id for item in key.items if item.trap}
    trap_hits = tuple(
        answer.id
        for item in key.items
        if item.clause_id in trap_ids
        and (answer := by_clause.get(item.clause_id)) is not None
        and answer.lane == "auto"
        and answer.verdict is not None
        and answer.verdict != item.status
    )
    used = {f.id for f in by_clause.values()}
    return Scorecard(
        items=items,
        false_positives=tuple(f.id for f in findings if f.id not in used),
        trap_hits=trap_hits,
        summary=_summary(key, by_clause),
    )


def load_s2_scorer(data_dir: Path) -> Scorer:
    titles = {clause.id: clause.title for clause in load_checklist(data_dir).clauses}
    text = load_s2_documents(data_dir).get(ADDENDUM_ID).text
    return partial(score, key=load_s2_key(data_dir), titles=titles, text=text)
