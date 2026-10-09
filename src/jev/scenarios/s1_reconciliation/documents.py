"""Load and validate the S1 synthetic documents and answer key."""

from pathlib import Path

from jev.budget.estimator import estimate_tokens
from jev.domain.documents import Document, DocumentSet
from jev.domain.money import format_money
from jev.scoring.answer_key import load_answer_key

SCENARIO_ID = "s1_reconciliation"
INVOICE_COUNT = 12
# Pessimistic token estimates per document. Each Jev state is one filtered document,
# far below Jev's 32k state limit; small states are also more accurate (jaggedness #5).
MAX_ESTIMATED_TOKENS = {"msa": 2_500, "invoice": 600}


class DocumentTooLargeError(ValueError):
    """A document exceeds its token budget; trim it before sending it to Jev."""


def scenario_dir(data_dir: Path) -> Path:
    return data_dir / "scenarios" / SCENARIO_ID


def _read(path: Path, doc_id: str, limit: int) -> Document:
    text = path.read_text(encoding="utf-8")
    if estimate_tokens(text) > limit:
        raise DocumentTooLargeError(f"{doc_id} is ~{estimate_tokens(text)} tokens (limit {limit})")
    return Document(doc_id=doc_id, text=text)


def load_s1_documents(data_dir: Path) -> DocumentSet:
    folder = scenario_dir(data_dir) / "documents"
    msa = _read(folder / "msa.md", "msa", MAX_ESTIMATED_TOKENS["msa"])
    invoices = [
        _read(
            folder / "invoices" / f"inv-2026-{m:02d}.md",
            f"inv-2026-{m:02d}",
            MAX_ESTIMATED_TOKENS["invoice"],
        )
        for m in range(1, INVOICE_COUNT + 1)
    ]
    return DocumentSet(documents=(msa, *invoices))


def validate_s1_data(data_dir: Path) -> list[str]:
    """Every answer-key value must be traceable to the documents. Returns a list of problems."""
    documents = load_s1_documents(data_dir)
    key = load_answer_key(scenario_dir(data_dir) / "answer_key.json")
    problems: list[str] = []
    for item in key.items:
        try:
            text = documents.get(item.doc_id).text
        except KeyError:
            problems.append(f"{item.id}: unknown document {item.doc_id}")
            continue
        if format_money(item.billed) not in text:
            problems.append(
                f"{item.id}: billed {format_money(item.billed)} not found in {item.doc_id}"
            )
        for evidence in item.evidence:
            try:
                source = documents.get(evidence.doc_id).text
            except KeyError:
                problems.append(f"{item.id}: unknown evidence document {evidence.doc_id}")
                continue
            if evidence.quote not in source:
                problems.append(
                    f"{item.id}: quote not found in {evidence.doc_id}: {evidence.quote!r}"
                )
    return problems
