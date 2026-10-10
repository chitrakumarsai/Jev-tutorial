"""Structured-output schema for the S2 LLM side: the same verdicts and risk levels as the key."""

from pydantic import BaseModel, ConfigDict

from jev.domain.findings import ClauseVerdict, Risk


class S2LlmClause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_id: str
    status: ClauseVerdict
    section: str | None  # e.g. "9.2"; null when absent
    quote: str | None  # verbatim from the addendum; null when absent
    risk: Risk
    explanation: str


class S2LlmReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clauses: list[S2LlmClause]
