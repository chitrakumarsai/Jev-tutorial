"""Recall-tuned regex finders. They over-find on purpose: distractors become candidates too,
and Jev picks among them (TypeSafe "pre-parsed value extraction" pattern)."""

import re
from dataclasses import dataclass
from datetime import date, datetime

from jev.domain.documents import Document
from jev.domain.findings import SpanRef

MONEY_RE = re.compile(r"\$\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\$\d+(?:\.\d{2})?", re.ASCII)
PERCENT_RE = re.compile(r"(?<![\d.])\d+(?:\.\d+)?%", re.ASCII)
# Whole numbers that are not part of money, percentages, decimals or clause numbers.
INTEGER_RE = re.compile(r"(?<![\d$.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?!\d|%|[.,]\d)", re.ASCII)
_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"\b\d{{1,2}} (?:{_MONTHS}) \d{{4}}\b")


@dataclass(frozen=True)
class Candidate:
    """A distinct value found in a document, with every place it occurs."""

    value: str
    spans: tuple[SpanRef, ...]

    def as_date(self) -> date:
        return datetime.strptime(self.value, "%d %B %Y").date()


def _find(document: Document, pattern: re.Pattern[str]) -> tuple[Candidate, ...]:
    spans: dict[str, list[SpanRef]] = {}
    for match in pattern.finditer(document.text):
        span = SpanRef(
            doc_id=document.doc_id, start=match.start(), end=match.end(), text=match.group()
        )
        spans.setdefault(match.group(), []).append(span)
    return tuple(Candidate(value=v, spans=tuple(s)) for v, s in spans.items())


def find_money(document: Document) -> tuple[Candidate, ...]:
    return _find(document, MONEY_RE)


def find_percents(document: Document) -> tuple[Candidate, ...]:
    return _find(document, PERCENT_RE)


def find_integers(document: Document) -> tuple[Candidate, ...]:
    return _find(document, INTEGER_RE)


def find_dates(document: Document) -> tuple[Candidate, ...]:
    return _find(document, DATE_RE)
