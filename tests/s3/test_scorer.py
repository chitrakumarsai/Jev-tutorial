"""S3 scoring: per memo citation, the verdict against the approved key."""

from typing import Any

import pytest

from jev.domain.findings import Finding
from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s3_citation_check.answer_key import load_s3_key
from jev.scenarios.s3_citation_check.documents import load_memo
from jev.scenarios.s3_citation_check.jev_pipeline import JevS3Pipeline
from jev.scenarios.s3_citation_check.scorer import load_s3_scorer
from jev.scoring.scorecard import Scorecard
from tests.s1.facts import DATA
from tests.s3.fake_jev import FakeS3Jev

KEY = load_s3_key(DATA)
SCORE = load_s3_scorer(DATA)


def findings(side: str = "jev", **changes: dict[str, Any]) -> list[Finding]:
    rows = []
    for i in KEY.items:
        fields: dict[str, Any] = {
            "id": f"{side}-{i.citation_id}",
            "kind": "citation",
            "doc_id": "msa",
            "verdict": i.verdict,
            "claim": "c",
        }
        rows.append(Finding(**{**fields, **(changes.get(i.citation_id) or {})}))
    return rows


def status(card: Scorecard, citation_id: str) -> str:
    key_id = next(i.id for i in KEY.items if i.citation_id == citation_id)
    return next(s.status for s in card.items if s.key_id == key_id)


def row(card: Scorecard, label: str) -> tuple[str | None, bool | None]:
    found = next(r for r in card.summary if r.label == label)
    return found.value, found.ok


def test_a_perfect_check_scores_every_citation() -> None:
    card = SCORE(findings())

    assert (card.correct, card.of, card.false_positives, card.trap_hits) == (10, 10, (), ())
    assert row(card, "Fabricated quote caught") == ("Yes", True)
    assert row(card, "Planted errors caught") == ("4 of 4", True)
    assert row(card, "Wrong verdicts") == ("0", True)
    assert {s.label for s in card.items} == {f"C{n}" for n in range(1, 11)}


def test_the_llm_side_is_scored_the_same_way() -> None:
    assert SCORE(findings("llm")).correct == 10


def test_a_correct_answer_in_review_is_counted_separately() -> None:
    card = SCORE(findings(C8={"lane": "review"}))

    assert status(card, "C8") == "correct_in_review"
    assert row(card, "Planted errors caught") == ("4 of 4", True)


def test_a_wrong_verdict_on_a_planted_error_is_a_trap_hit_when_confident() -> None:
    confident = SCORE(findings(C7={"verdict": "verified"}))
    in_review = SCORE(findings(C7={"verdict": "verified", "lane": "review"}))

    assert status(confident, "C7") == "wrong_value"
    assert confident.trap_hits == ("jev-C7",)
    assert in_review.trap_hits == ()
    assert row(confident, "Planted errors caught") == ("3 of 4", False)
    assert row(confident, "Wrong verdicts") == ("1", False)


def test_missing_the_fabricated_quote_is_flagged() -> None:
    card = SCORE(findings(C3={"verdict": "verified"}))

    assert row(card, "Fabricated quote caught") == ("No", False)


@pytest.mark.parametrize("change", [{"verdict": None}, None])
def test_no_verdict_or_no_finding_is_missed(change: dict[str, Any] | None) -> None:
    rows = findings(C5=change) if change else [f for f in findings() if f.id != "jev-C5"]

    assert status(SCORE(rows), "C5") == "missed"


def test_findings_for_unknown_or_repeated_citations_are_false_positives() -> None:
    rows = findings()
    extra = [rows[0].model_copy(update={"id": "jev-C99"}), rows[1].model_copy()]

    card = SCORE([*rows, *extra])

    assert set(card.false_positives) == {"jev-C99"} | {rows[1].id}
    assert card.correct == 10


async def test_the_jev_pipeline_with_a_reader_like_the_key_scores_full_marks() -> None:
    pipeline = JevS3Pipeline(
        load_s1_documents(DATA), load_memo(DATA), review_threshold=0.8, run_id="r1"
    )
    output = await pipeline.run(FakeS3Jev(KEY), lambda *event: None)

    assert SCORE(output.findings).correct == 10
