"""Check the S2 addendum, checklist and answer key against each other before any model run."""

from pathlib import Path

from jev.scenarios.s2_clause_review.answer_key import load_s2_key
from jev.scenarios.s2_clause_review.checklist import load_checklist
from jev.scenarios.s2_clause_review.documents import ADDENDUM_ID, load_s2_documents


def validate_s2_data(data_dir: Path) -> list[str]:
    """The key covers the checklist exactly, quotes sit on their lines, and an absent clause's
    wording appears nowhere. Returns a list of problems."""
    lines = load_s2_documents(data_dir).get(ADDENDUM_ID).text.splitlines()
    text = "\n".join(lines).lower()
    clauses = {clause.id: clause for clause in load_checklist(data_dir).clauses}
    key = load_s2_key(data_dir)
    problems = [
        f"{clause_id}: in the checklist but not in the answer key"
        for clause_id in clauses.keys() - {item.clause_id for item in key.items}
    ]
    for item in key.items:
        clause = clauses.get(item.clause_id)
        if clause is None:
            problems.append(f"{item.id}: {item.clause_id} is not in the checklist")
        elif item.status == "absent":
            found = [p for p in clause.absence_phrases if p.lower() in text]
            if found:
                problems.append(f"{item.id}: {item.clause_id} is keyed absent but has {found}")
        elif item.first_line and item.last_line and item.quote:
            span = lines[item.first_line - 1 : item.last_line]
            if not any(item.quote in line for line in span):
                problems.append(
                    f"{item.id}: {item.clause_id} quote not within lines "
                    f"{item.first_line}-{item.last_line}: {item.quote!r}"
                )
    return problems
