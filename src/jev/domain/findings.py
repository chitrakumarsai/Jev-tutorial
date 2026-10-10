"""A finding reported by either side of a run, in one shape so both are scored the same way."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Lane = Literal["auto", "review"]
# S2: is the checklist clause in the agreement? S3: does the citation hold up?
Verdict = Literal[
    "present", "absent", "partial", "verified", "unsupported", "contradicted", "fabricated"
]
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
    risk: Risk | None = None  # S2 only, and only for a clause that is present
    claim: str | None = None  # S3: the memo's claim the citation is meant to support
