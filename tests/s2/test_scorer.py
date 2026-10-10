"""S2 scoring: per checklist clause, verdict, location, risk and traceability against the key."""

from pathlib import Path
from typing import Any

import pytest

from jev.domain.findings import Finding, SpanRef
from jev.scenarios.s2_clause_review.answer_key import S2KeyItem, load_s2_key
from jev.scenarios.s2_clause_review.checklist import load_checklist
from jev.scenarios.s2_clause_review.documents import load_s2_documents
from jev.scenarios.s2_clause_review.jev_pipeline import JevS2Pipeline
from jev.scenarios.s2_clause_review.scorer import load_s2_scorer
from jev.scoring.scorecard import Scorecard
from tests.s2.fake_jev import FakeS2Jev

DATA = Path(__file__).resolve().parents[2] / "data"
KEY = load_s2_key(DATA)
SCORE = load_s2_scorer(DATA)
SPAN = SpanRef(doc_id="addendum", start=0, end=1, text="#")


def finding(item: S2KeyItem, **changes: Any) -> Finding:
    """A finding that matches the key item exactly, unless changed."""
    located = item.status != "absent"
    fields: dict[str, Any] = {
        "id": f"f-{item.clause_id}",
        "kind": item.clause_id,
        "doc_id": "addendum",
        "verdict": item.status,
        "risk": item.risk,
        "line_ref": f"L{item.first_line:03d}" if located and item.first_line else None,
        "evidence": (SPAN,) if located else (),
    }
    return Finding(**{**fields, **changes})


def perfect(**per_clause: dict[str, Any]) -> list[Finding]:
    return [finding(item, **per_clause.get(item.clause_id, {})) for item in KEY.items]


def status(card: Scorecard, clause_id: str) -> str:
    key_id = next(item.id for item in KEY.items if item.clause_id == clause_id)
    return next(i.status for i in card.items if i.key_id == key_id)


def row(card: Scorecard, label: str) -> tuple[str | None, bool | None]:
    found = next(r for r in card.summary if r.label == label)
    return found.value, found.ok


def test_a_perfect_review_scores_every_clause_and_names_it() -> None:
    card = SCORE(perfect())

    assert (card.correct, card.of, card.false_positives, card.trap_hits) == (10, 10, (), ())
    titles = {c.title for c in load_checklist(DATA).clauses}
    assert {item.label for item in card.items} == titles
    assert row(card, "Missing clause caught") == ("Yes", True)
    assert row(card, "Wrong verdicts") == ("0", True)
    assert row(card, "Wrong risk levels") == ("0", True)


def test_a_correct_answer_in_the_review_lane_is_counted_separately() -> None:
    card = SCORE(perfect(audit_rights={"lane": "review"}))

    assert status(card, "audit_rights") == "correct_in_review"
    assert (card.correct, card.correct_in_review) == (9, 1)


@pytest.mark.parametrize(
    ("clause", "changes"),
    [
        ("indemnity", {"verdict": "partial"}),
        ("indemnity", {"risk": "critical"}),
        ("indemnity", {"line_ref": "L090"}),
        ("indemnity", {"traceable": False, "evidence": ()}),
    ],
)
def test_any_wrong_part_makes_the_clause_wrong(clause: str, changes: dict[str, Any]) -> None:
    card = SCORE(perfect(**{clause: changes}))

    assert status(card, clause) == "wrong_value"


def test_an_absent_clause_needs_no_location() -> None:
    card = SCORE(perfect(breach_notification={"line_ref": None, "evidence": ()}))

    assert status(card, "breach_notification") == "correct"


def test_inventing_the_missing_clause_is_a_trap_hit() -> None:
    invented = {"verdict": "present", "risk": "medium", "line_ref": "L089", "traceable": False}

    card = SCORE(perfect(breach_notification=invented))

    assert status(card, "breach_notification") == "wrong_value"
    assert card.trap_hits == ("f-breach_notification",)
    assert row(card, "Missing clause caught") == ("No", False)
    assert row(card, "Wrong verdicts") == ("1", False)


def test_missing_findings_and_unknown_verdicts_are_missed() -> None:
    findings = [f for f in perfect() if f.kind != "insurance"]
    findings = [
        f.model_copy(update={"verdict": None, "risk": None}) if f.kind == "indemnity" else f
        for f in findings
    ]

    card = SCORE(findings)

    assert status(card, "insurance") == status(card, "indemnity") == "missed"


def test_findings_for_clauses_outside_the_key_are_false_positives() -> None:
    stray = Finding(id="stray", kind="force_majeure", doc_id="addendum", verdict="present")

    card = SCORE([*perfect(), stray])

    assert card.false_positives == ("stray",)


async def test_the_jev_pipeline_with_a_good_reader_scores_full_marks() -> None:
    docs = load_s2_documents(DATA)
    pipeline = JevS2Pipeline(docs, load_checklist(DATA), review_threshold=0.8, run_id="r1")

    output = await pipeline.run(FakeS2Jev(KEY), lambda *event: None)
    card = SCORE(output.findings)

    assert (card.correct + card.correct_in_review, card.of) == (10, 10)
    assert card.correct_in_review == 2  # the two partial clauses go to review
