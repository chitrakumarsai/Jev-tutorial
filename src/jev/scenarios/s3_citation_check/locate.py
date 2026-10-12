"""Find where a citation's quote really is: its span, the whole lines holding it (the passage
that is judged), and, for the agreement, which clause that is versus the one cited."""

import re
from dataclasses import dataclass

from jev.domain.documents import DocumentSet
from jev.domain.findings import SpanRef
from jev.scenarios.s3_citation_check.memo_draft import MemoCitation

AGREEMENT_ID = "msa"
_CLAUSE = re.compile(r"(\d+\.\d+)\s+[A-Za-z]")  # "3.1 Line-haul rates. ..."
_CITED = re.compile(r"(?:§|section|cl\.?)\s*(\d+\.\d+)", re.IGNORECASE)  # "§3.1", "Section 3.1"


@dataclass(frozen=True)
class Located:
    span: SpanRef
    passage: str  # the full lines holding the quote
    actual_section: str | None  # "§3.1" for an agreement clause; None for invoice rows
    section_ok: bool  # the cited section holds the quote (invoice rows count as correct)


def _quote_pattern(quote: str) -> re.Pattern[str] | None:
    """Exact words in order; whitespace differences are tolerated (as find_quote)."""
    words = quote.split()
    return re.compile(r"\s+".join(re.escape(w) for w in words)) if words else None


def _passage(text: str, start: int, end: int) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    return text[line_start : len(text) if line_end == -1 else line_end].rstrip("\r")


def _clause(passage: str) -> str | None:
    match = _CLAUSE.match(passage)
    return f"§{match[1]}" if match else None


def locate(citation: MemoCitation, documents: DocumentSet) -> Located | None:
    """None when the quote is not in the cited document: a fabricated quote. A quote found
    more than once is taken from the cited clause when it is there."""
    try:
        text = documents.get(citation.doc_id).text
    except KeyError:
        return None
    pattern = _quote_pattern(citation.quote)
    matches = list(pattern.finditer(text)) if pattern else []
    if not matches:
        return None
    cited_match = _CITED.search(citation.section)
    cited = f"§{cited_match[1]}" if cited_match else None
    is_agreement = citation.doc_id == AGREEMENT_ID
    chosen = next(
        (
            m
            for m in matches
            if is_agreement and cited and _clause(_passage(text, m.start(), m.end())) == cited
        ),
        matches[0],
    )
    span = SpanRef(
        doc_id=citation.doc_id, start=chosen.start(), end=chosen.end(), text=chosen.group()
    )
    passage = _passage(text, chosen.start(), chosen.end())
    if not is_agreement:
        return Located(span, passage, None, True)
    actual = _clause(passage)
    return Located(span, passage, actual, actual is not None and actual == cited)
