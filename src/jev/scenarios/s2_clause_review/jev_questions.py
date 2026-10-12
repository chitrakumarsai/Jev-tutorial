"""S2 questions for Jev, after the semantic-find recipe: the addendum is sent once with every
line numbered, and for each checklist clause Jev answers three questions in parallel: which line
addresses it (Choice), whether it is present, partial or absent (Choice, with the same
definitions the LLM gets), and how risky it is (Score)."""

import re
from dataclasses import dataclass

from pydantic import JsonValue

from jev.domain.documents import Document
from jev.providers.jev.types import ChoiceQ, Description, JevRequest, Question, ScoreQ
from jev.scenarios.s2_clause_review.checklist import Checklist, ChecklistClause
from jev.scenarios.s2_clause_review.verdicts import STATUS_DEFINITIONS

CLAUSES_PURPOSE = "s2.clauses"


_SECTION = re.compile(r"##\s+(\d+)\.")
# Headings, the synthetic-data note and header fields ("**Parties:** ...") are not provisions.
_NOT_PROVISION = ("#", ">", "**")


@dataclass(frozen=True)
class NumberedLine:
    id: str  # "L068": the 1-based line number in the addendum file, as the answer key uses
    text: str
    start: int  # character offsets into the document, for evidence spans
    end: int
    section: str | None  # the "## N." section the line sits in, e.g. "9"; None before any

    @property
    def is_provision(self) -> bool:
        return not self.text.lstrip().startswith(_NOT_PROVISION)


def numbered_lines(doc: Document) -> list[NumberedLine]:
    lines: list[NumberedLine] = []
    offset = 0
    section: str | None = None
    # Only "\n" ends a line, as in the answer key's numbering; splitlines() would also split
    # on form feeds and Unicode separators and shift every later line number.
    for number, raw in enumerate(doc.text.split("\n"), start=1):
        text = raw.rstrip("\r")
        heading = _SECTION.match(text.strip())
        section = heading.group(1) if heading else section
        if text.strip():
            lines.append(NumberedLine(f"L{number:03d}", text, offset, offset + len(text), section))
        offset += len(raw) + 1
    return lines


_STATUS_OPTIONS: dict[str, Description | None] = dict(STATUS_DEFINITIONS.items())


def _questions(clause: ChecklistClause, line_ids: list[str]) -> dict[str, Question]:
    subject = f"{clause.title}: {clause.look_for}"
    return {
        f"{clause.id}__where": ChoiceQ(
            instructions=f"Which line of the `addendum` best addresses this? {subject}",
            criteria=dict.fromkeys(line_ids),
        ),
        f"{clause.id}__status": ChoiceQ(
            instructions=f"Is this in the `addendum`? {subject}",
            criteria=_STATUS_OPTIONS,
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
    # Jev may only point at a provision, as the LLM may only quote one (8+ words).
    line_ids = [line.id for line in lines if line.is_provision]
    questions: dict[str, Question] = {}
    for clause in checklist.clauses:
        questions.update(_questions(clause, line_ids))
    state: dict[str, JsonValue] = {
        "addendum": "\n".join(f"{line.id}| {line.text}" for line in lines)
    }
    return JevRequest(state=state, questions=questions, purpose=CLAUSES_PURPOSE, run_id=run_id)
