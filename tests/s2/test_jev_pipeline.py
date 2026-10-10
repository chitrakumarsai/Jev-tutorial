"""S2 on the Jev side: Jev judges where, whether and how risky; code decides the verdict and
gates anything uncertain or partial to the auditor review lane."""

from pathlib import Path
from typing import Any

import pytest

from jev.domain.documents import Document
from jev.scenarios.s2_clause_review.answer_key import load_s2_key
from jev.scenarios.s2_clause_review.checklist import load_checklist
from jev.scenarios.s2_clause_review.documents import ADDENDUM_ID, load_s2_documents
from jev.scenarios.s2_clause_review.jev_pipeline import JevS2Pipeline
from jev.scenarios.s2_clause_review.jev_questions import numbered_lines
from tests.s2.fake_jev import FakeS2Jev

DATA = Path(__file__).resolve().parents[2] / "data"
DOCS = load_s2_documents(DATA)
CHECKLIST = load_checklist(DATA)
KEY = load_s2_key(DATA)


def pipeline() -> JevS2Pipeline:
    return JevS2Pipeline(DOCS, CHECKLIST, review_threshold=0.8, run_id="r1")


async def run(fake: FakeS2Jev) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    output = await pipeline().run(fake, lambda type_, side, data: events.append((type_, data)))
    return output, events


async def test_a_good_reader_reproduces_every_verdict_and_risk_in_the_key() -> None:
    output, _ = await run(FakeS2Jev(KEY))

    found = {f.kind: f for f in output.findings}
    assert len(found) == len(KEY.items)
    for item in KEY.items:
        assert (found[item.clause_id].verdict, found[item.clause_id].risk) == (
            item.status,
            item.risk,
        )


async def test_a_located_clause_points_at_its_line_and_an_absent_one_at_nothing() -> None:
    output, _ = await run(FakeS2Jev(KEY))
    found = {f.kind: f for f in output.findings}
    text = DOCS.get(ADDENDUM_ID).text

    liability = found["limitation_of_liability"]
    assert liability.line_ref == "L068"
    (span,) = liability.evidence
    assert text[span.start : span.end] == span.text and "total liability" in span.text
    breach = found["breach_notification"]
    assert (breach.line_ref, breach.evidence) == (None, ())


async def test_partial_clauses_go_to_review_and_confident_answers_stay_auto() -> None:
    output, _ = await run(FakeS2Jev(KEY))

    lanes = {f.kind: (f.lane, f.review_reason) for f in output.findings}
    assert lanes["audit_rights"][0] == "review"
    assert str(lanes["audit_rights"][1]).startswith("partial:")
    assert lanes["insurance"][0] == "review"
    assert lanes["breach_notification"] == ("auto", None)
    assert lanes["governing_law"] == ("auto", None)


async def test_low_confidence_goes_to_review_with_the_reason() -> None:
    output, _ = await run(FakeS2Jev(KEY, confidence=0.6))

    governing = next(f for f in output.findings if f.kind == "governing_law")
    assert governing.lane == "review"
    assert "is below 80%" in str(governing.review_reason)
    assert governing.confidence is not None and governing.confidence < 0.8


async def test_a_risk_tie_is_resolved_to_the_higher_risk() -> None:
    fake = FakeS2Jev(KEY, risk_probabilities={"indemnity__risk": {"0": 0.5, "2": 0.5}})

    output, _ = await run(fake)

    assert next(f for f in output.findings if f.kind == "indemnity").risk == "high"


async def test_a_missing_answer_is_sent_to_review_not_guessed() -> None:
    fake = FakeS2Jev(KEY, omitted={"insurance__risk", "subcontracting__exists"})

    output, _ = await run(fake)
    found = {f.kind: f for f in output.findings}

    assert (found["insurance"].lane, found["insurance"].risk) == ("review", None)
    assert "no answer" in str(found["insurance"].review_reason)
    assert found["subcontracting"].lane == "review"
    assert found["subcontracting"].verdict is None


async def test_one_request_and_the_events_the_ui_plays() -> None:
    fake = FakeS2Jev(KEY)

    output, events = await run(fake)

    assert len(fake.requests) == 1
    steps = [data.get("step", type_) for type_, data in events]
    assert steps[:4] == ["candidates", "request_sent", "answers", "computed"]
    assert steps[4 : 4 + len(KEY.items)] == ["finding"] * len(KEY.items)
    assert steps[-1] == "gated"
    assert events[-1][1]["review"] == sum(f.lane == "review" for f in output.findings)
    assert output.models == ("jev-1.13.0",)
    assert output.usages[0].input_tokens == 2_400


async def test_every_evidence_span_is_the_text_at_its_offsets() -> None:
    output, _ = await run(FakeS2Jev(KEY))
    text = DOCS.get(ADDENDUM_ID).text

    spans = [span for f in output.findings for span in f.evidence]
    assert spans and all(text[s.start : s.end] == s.text for s in spans)


@pytest.mark.parametrize(
    ("noul", "verdict"),
    [(0.7, "present"), (0.699, "partial"), (0.35, "partial"), (0.349, "absent")],
)
async def test_the_verdict_thresholds_are_exact(noul: float, verdict: str) -> None:
    output, _ = await run(FakeS2Jev(KEY, nouls={"governing_law__exists": noul}))

    assert next(f for f in output.findings if f.kind == "governing_law").verdict == verdict


@pytest.mark.parametrize("probabilities", [{"x": 1.0}, {}, {"7": 1.0}, {"1.0": 1.0}])
async def test_an_unreadable_risk_answer_goes_to_review_instead_of_crashing(
    probabilities: dict[str, float],
) -> None:
    fake = FakeS2Jev(KEY, risk_probabilities={"indemnity__risk": probabilities})

    output, events = await run(fake)
    indemnity = next(f for f in output.findings if f.kind == "indemnity")

    assert (indemnity.lane, indemnity.risk) == ("review", None)
    assert "risk answer" in str(indemnity.review_reason)
    assert len(output.findings) == len(KEY.items)
    assert events[-1][1]["step"] == "gated"


async def test_a_line_jev_made_up_is_sent_to_review() -> None:
    output, _ = await run(FakeS2Jev(KEY, lines={"governing_law__where": "L999"}))

    governing = next(f for f in output.findings if f.kind == "governing_law")
    assert (governing.lane, governing.line_ref, governing.evidence) == ("review", None, ())
    assert "not in the document" in str(governing.review_reason)


async def test_the_low_confidence_reason_names_the_weak_question() -> None:
    fake = FakeS2Jev(KEY, where_confidence={"governing_law__where": 0.62})

    output, _ = await run(fake)
    governing = next(f for f in output.findings if f.kind == "governing_law")

    assert governing.lane == "review"
    assert "where 62% is below 80%" in str(governing.review_reason)
    assert governing.confidence == pytest.approx(0.62)


async def test_a_partial_clause_reports_its_other_answers_confidence_and_their_doubts() -> None:
    fake = FakeS2Jev(KEY, where_confidence={"audit_rights__where": 0.5})

    output, _ = await run(fake)
    audit = next(f for f in output.findings if f.kind == "audit_rights")

    reason = str(audit.review_reason)
    assert reason.startswith("partial:") and "where 50% is below 80%" in reason
    assert audit.confidence == pytest.approx(0.5)  # not ~0 from the coin-flip "exists" answer


async def test_a_near_tie_in_risk_goes_to_the_higher_level() -> None:
    fake = FakeS2Jev(KEY, risk_probabilities={"indemnity__risk": {"0": 0.47, "3": 0.45}})

    output, _ = await run(fake)

    assert next(f for f in output.findings if f.kind == "indemnity").risk == "critical"


def test_only_newlines_split_lines_so_numbering_matches_the_file() -> None:
    doc = Document(doc_id=ADDENDUM_ID, text="a\x0cstill line one\nline two\r\n\nline four\n")

    lines = numbered_lines(doc)

    assert [(line.id, line.text) for line in lines] == [
        ("L001", "a\x0cstill line one"),
        ("L002", "line two"),
        ("L004", "line four"),
    ]
    assert all(doc.text[line.start : line.end] == line.text for line in lines)
