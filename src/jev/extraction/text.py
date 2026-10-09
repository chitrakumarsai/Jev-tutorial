"""Locate a quoted passage in the source documents (citation check, LLM traceability)."""

import re

from jev.domain.documents import DocumentSet
from jev.domain.findings import SpanRef


def find_quote(documents: DocumentSet, quote: str) -> SpanRef | None:
    """Exact words in order; whitespace differences are tolerated, paraphrase is not."""
    words = quote.split()
    if not words:
        return None
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words))
    for document in documents.documents:
        match = pattern.search(document.text)
        if match:
            return SpanRef(
                doc_id=document.doc_id, start=match.start(), end=match.end(), text=match.group()
            )
    return None
