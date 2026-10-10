"""S2 questions for Jev, after the semantic-find recipe: the addendum is sent once with every
line numbered, and for each checklist clause Jev answers three questions in parallel:
which line addresses it (Choice), whether any line does (Noul), and how risky it is (Score)."""

from dataclasses import dataclass

from pydantic import JsonValue

from jev.domain.documents import Document
from jev.providers.jev.types import ChoiceQ, JevRequest, NoulCriteriaQ, NoulQ, Question, ScoreQ
from jev.scenarios.s2_clause_review.checklist import Checklist, ChecklistClause

CLAUSES_PURPOSE = "s2.clauses"


@dataclass(frozen=True)
class NumberedLine:
    id: str  # "L068": the 1-based line number in the addendum file, as the answer key uses
    text: str
    start: int  # character offsets into the document, for evidence spans
    end: int


def numbered_lines(doc: Document) -> list[NumberedLine]:
    lines: list[NumberedLine] = []
    offset = 0
    for number, raw in enumerate(doc.text.splitlines(keepends=True), start=1):
        text = raw.rstrip("\r\n")
        if text.strip():
            lines.append(NumberedLine(f"L{number:03d}", text, offset, offset + len(text)))
        offset += len(raw)
    return lines


def _questions(clause: ChecklistClause, line_ids: list[str]) -> dict[str, Question]:
    subject = f"{clause.title}: {clause.look_for}"
    return {
        f"{clause.id}__where": ChoiceQ(
            instructions=f"Which line of the `addendum` best addresses this? {subject}",
            criteria=dict.fromkeys(line_ids),
        ),
        f"{clause.id}__exists": NoulQ(
            instructions=f"Does any line of the `addendum` actually provide this? {subject}",
            criteria=NoulCriteriaQ(
                true="A line in the addendum provides this.",
                false="No line provides this; related wording that does not do it does not count.",
            ),
        ),
        f"{clause.id}__risk": ScoreQ(
            instructions=(
                f"How risky for the Customer are the `addendum`'s terms on {clause.title}? "
                "If the addendum has no such terms, judge that absence."
            ),
            criteria=clause.risk_rubric,
        ),
    }


def clause_request(doc: Document, checklist: Checklist, *, run_id: str) -> JevRequest:
    lines = numbered_lines(doc)
    line_ids = [line.id for line in lines]
    questions: dict[str, Question] = {}
    for clause in checklist.clauses:
        questions.update(_questions(clause, line_ids))
    state: dict[str, JsonValue] = {
        "addendum": "\n".join(f"{line.id}| {line.text}" for line in lines)
    }
    return JevRequest(state=state, questions=questions, purpose=CLAUSES_PURPOSE, run_id=run_id)
