"""A finding reported by either side of a run, in one shape so both are scored the same way."""

from decimal import Decimal
from typing import Literal, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

Lane = Literal["auto", "review"]
# S2: is the checklist clause in the agreement? S3: does the citation hold up?
ClauseVerdict = Literal["present", "absent", "partial"]
CitationVerdict = Literal["verified", "unsupported", "contradicted", "fabricated"]
Verdict = ClauseVerdict | CitationVerdict
CLAUSE_VERDICTS: frozenset[str] = frozenset(get_args(ClauseVerdict))
CITATION_VERDICTS: frozenset[str] = frozenset(get_args(CitationVerdict))
Risk = Literal["low", "medium", "high", "critical"]  # S2 clause risk rubric


class SpanRef(BaseModel):
    """Where a value or quote came from: document id plus character offsets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_id: str
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str


class Finding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    kind: str
    doc_id: str
    line_ref: str | None = None
    billed: Decimal | None = None
    expected: Decimal | None = None
    variance: Decimal | None = None
    lane: Lane = "auto"
    confidence: float | None = Field(default=None, ge=0, le=1)
    review_reason: str | None = None
    evidence: tuple[SpanRef, ...] = ()
    traceable: bool = True  # False when a quoted source can't be found verbatim
    verdict: Verdict | None = None  # S2 and S3 only
    risk: Risk | None = None  # S2 only: a present or partial clause; None when absent
    claim: str | None = None  # S3 only: the memo's claim the citation is meant to support

    @model_validator(mode="after")
    def _fields_fit_the_verdict(self) -> Self:
        """Only the checks that need no scenario knowledge; pipelines own the rest."""
        if self.risk is not None and self.verdict not in CLAUSE_VERDICTS - {"absent"}:
            raise ValueError(f"A risk level does not fit verdict {self.verdict!r}")
        if self.claim is not None and self.verdict in CLAUSE_VERDICTS:
            raise ValueError(f"A claim does not fit verdict {self.verdict!r}")
        return self
