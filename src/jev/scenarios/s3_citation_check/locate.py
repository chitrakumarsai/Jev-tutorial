"""Find where a citation's quote really is: its span, the whole lines holding it (the passage
that is judged), and, for the agreement, which clause that is versus the one cited."""

import re
from dataclasses import dataclass

from jev.domain.documents import DocumentSet
from jev.domain.findings import SpanRef
from jev.extraction.text import find_quote
from jev.scenarios.s3_citation_check.memo_draft import MemoCitation

AGREEMENT_ID = "msa"
_CLAUSE = re.compile(r"(\d+\.\d+)\s")  # "3.1 Line-haul rates. ..."
_CITED = re.compile(r"§\s*(\d+\.\d+)")  # "§3.1"


@dataclass(frozen=True)
class Located:
    span: SpanRef
    passage: str  # the full lines holding the quote
    actual_section: str | None  # "§3.1" for an agreement clause; None for invoice rows
    section_ok: bool  # the cited section holds the quote (invoice rows count as correct)


def locate(citation: MemoCitation, documents: DocumentSet) -> Located | None:
    """None when the quote is not in the cited document: a fabricated quote."""
    try:
        document = documents.get(citation.doc_id)
    except KeyError:
        return None
    span = find_quote(DocumentSet(documents=(document,)), citation.quote)
    if span is None:
        return None
    text = document.text
    start = text.rfind("\n", 0, span.start) + 1
    end = text.find("\n", span.end)
    passage = text[start : len(text) if end == -1 else end]
    if citation.doc_id != AGREEMENT_ID:
        return Located(span, passage, None, True)
    clause, cited = _CLAUSE.match(passage), _CITED.search(citation.section)
    actual = f"§{clause[1]}" if clause else None
    return Located(
        span, passage, actual, actual is not None and cited is not None and actual == f"§{cited[1]}"
    )
