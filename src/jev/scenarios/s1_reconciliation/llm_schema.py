"""Structured-output schema for the LLM side. Same finding kinds the Jev side reports."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

LlmFindingKind = Literal[
    "discount_not_applied",
    "surcharge_on_undiscounted_base",
    "surcharge_over_cap",
    "duplicate_line",
    "late_fee_incorrect",
    "rate_mismatch",
    "other",
]


class LlmFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: LlmFindingKind
    invoice_id: str
    line_ref: str
    billed: str
    expected: str
    variance: str
    quote: str
    explanation: str


class S1LlmReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[LlmFinding]
    total_variance: str
