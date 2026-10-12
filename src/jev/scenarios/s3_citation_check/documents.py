"""S3 inputs: the S1 documents (the memo's sources) and the planted memo itself."""

from pathlib import Path

from jev.domain.documents import Document, DocumentSet
from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s3_citation_check.memo_draft import MemoDraft

SCENARIO_ID = "s3_citation_check"
MEMO_ID = "memo"  # shown in the document viewer; never given to either side as a source


def scenario_dir(data_dir: Path) -> Path:
    return data_dir / "scenarios" / SCENARIO_ID


def load_memo(data_dir: Path) -> MemoDraft:
    """The memo with the presenter's planted errors (memo_draft.json is the LLM original)."""
    return MemoDraft.model_validate_json((scenario_dir(data_dir) / "memo.json").read_text("utf-8"))


def load_s3_documents(data_dir: Path) -> DocumentSet:
    """The S1 documents (the memo's sources) plus the memo itself, for the document viewer."""
    memo = (scenario_dir(data_dir) / "memo.md").read_text("utf-8")
    sources = load_s1_documents(data_dir)
    return DocumentSet(documents=(*sources.documents, Document(doc_id=MEMO_ID, text=memo)))


def sources_only(documents: DocumentSet) -> DocumentSet:
    """The documents the citations may quote: everything except the memo."""
    return DocumentSet(documents=tuple(d for d in documents.documents if d.doc_id != MEMO_ID))
