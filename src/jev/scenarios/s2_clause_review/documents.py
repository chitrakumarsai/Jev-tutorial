"""Load and validate the S2 addendum, checklist and answer key."""

from pathlib import Path

from jev.budget.estimator import estimate_tokens
from jev.domain.documents import Document, DocumentSet
from jev.providers.jev.types import MAX_CHOICE_OPTIONS

SCENARIO_ID = "s2_clause_review"
ADDENDUM_ID = "addendum"
# One Jev state holds the whole line-numbered addendum: far below Jev's 32k state limit.
MAX_ESTIMATED_TOKENS = 3_000


class DocumentTooLargeError(ValueError):
    """The addendum is too long for one state, or for one Choice over its lines."""


def scenario_dir(data_dir: Path) -> Path:
    return data_dir / "scenarios" / SCENARIO_ID


def load_s2_documents(data_dir: Path) -> DocumentSet:
    text = (scenario_dir(data_dir) / "documents" / "addendum.md").read_text(encoding="utf-8")
    tokens = estimate_tokens(text)
    if tokens > MAX_ESTIMATED_TOKENS:
        raise DocumentTooLargeError(f"addendum is ~{tokens} tokens (limit {MAX_ESTIMATED_TOKENS})")
    if len(text.split("\n")) > MAX_CHOICE_OPTIONS:
        raise DocumentTooLargeError(f"addendum has more than {MAX_CHOICE_OPTIONS} lines")
    return DocumentSet(documents=(Document(doc_id=ADDENDUM_ID, text=text),))
