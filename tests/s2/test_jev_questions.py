"""S2 Jev questions: one line-numbered state, three parallel questions per checklist clause."""

from pathlib import Path

from jev.providers.jev.types import MAX_CHOICE_OPTIONS, ChoiceQ, ScoreQ
from jev.scenarios.s2_clause_review.checklist import load_checklist
from jev.scenarios.s2_clause_review.documents import ADDENDUM_ID, load_s2_documents
from jev.scenarios.s2_clause_review.jev_questions import (
    CLAUSES_PURPOSE,
    clause_request,
    numbered_lines,
)

DATA = Path(__file__).resolve().parents[2] / "data"
ADDENDUM = load_s2_documents(DATA).get(ADDENDUM_ID)
CHECKLIST = load_checklist(DATA)


def test_lines_are_numbered_from_one_like_the_answer_key_and_blank_lines_are_skipped() -> None:
    lines = numbered_lines(ADDENDUM)
    by_id = {line.id: line for line in lines}

    assert "9.2 Each party's total liability" in by_id["L068"].text
    assert all(line.text.strip() for line in lines)
    assert ADDENDUM.text[by_id["L068"].start : by_id["L068"].end] == by_id["L068"].text


def test_one_request_asks_where_whether_and_how_risky_for_every_clause() -> None:
    request = clause_request(ADDENDUM, CHECKLIST, run_id="r1")

    assert request.purpose == CLAUSES_PURPOSE
    assert len(request.questions) == 3 * len(CHECKLIST.clauses)
    for clause in CHECKLIST.clauses:
        where = request.questions[f"{clause.id}__where"]
        status = request.questions[f"{clause.id}__status"]
        risk = request.questions[f"{clause.id}__risk"]
        assert isinstance(where, ChoiceQ) and isinstance(status, ChoiceQ)
        assert list(status.criteria) == ["present", "partial", "absent"]
        assert isinstance(risk, ScoreQ)
        assert risk.criteria == clause.risk_rubric  # low first, critical last
        assert clause.title in str(where.instructions)


def test_the_state_carries_every_numbered_line_once() -> None:
    request = clause_request(ADDENDUM, CHECKLIST, run_id="r1")
    state = request.state
    assert isinstance(state, dict)
    text = str(state["addendum"])

    assert "L068| 9.2 Each party's total liability" in text
    where = request.questions[f"{CHECKLIST.clauses[0].id}__where"]
    assert isinstance(where, ChoiceQ)
    provisions = [line for line in numbered_lines(ADDENDUM) if line.is_provision]
    assert len(where.criteria) == len(provisions) <= MAX_CHOICE_OPTIONS


def test_jev_gets_the_same_status_definitions_as_the_llm_prompt() -> None:
    from jev.scenarios.s2_clause_review.llm_pipeline import INSTRUCTIONS

    request = clause_request(ADDENDUM, CHECKLIST, run_id="r1")
    status = request.questions[f"{CHECKLIST.clauses[0].id}__status"]
    assert isinstance(status, ChoiceQ)

    flat = " ".join(INSTRUCTIONS.split())
    for description in status.criteria.values():
        assert isinstance(description, str)
        assert description in flat


def test_jev_may_only_point_at_provision_lines_not_headings_or_header_fields() -> None:
    request = clause_request(ADDENDUM, CHECKLIST, run_id="r1")
    where = request.questions[f"{CHECKLIST.clauses[0].id}__where"]
    assert isinstance(where, ChoiceQ)
    by_id = {line.id: line for line in numbered_lines(ADDENDUM)}

    options = [by_id[line_id].text for line_id in where.criteria]
    assert "L040" not in where.criteria  # "## 5. Audit"
    assert not any(t.startswith(("#", ">", "**")) for t in options)
    assert "L042" in where.criteria and "L068" in where.criteria
    state = request.state
    assert isinstance(state, dict) and "L040| ## 5. Audit" in str(state["addendum"])


def test_every_line_knows_its_section() -> None:
    by_id = {line.id: line for line in numbered_lines(ADDENDUM)}

    assert by_id["L067"].section == by_id["L068"].section == "9"
    assert by_id["L074"].section == "10"
    assert by_id["L001"].section is None  # the title, before any section
