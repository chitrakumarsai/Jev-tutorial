"""A finding reported by either side of a run, in one shape so both are scored the same way."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Lane = Literal["auto", "review"]


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
