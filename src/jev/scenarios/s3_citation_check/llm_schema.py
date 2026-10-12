"""Structured-output schema for the S3 LLM side: the same verdicts as the key and Jev."""

from pydantic import BaseModel, ConfigDict

from jev.domain.findings import CitationVerdict


class S3LlmCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: str
    verdict: CitationVerdict
    reason: str


class S3LlmReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citations: list[S3LlmCitation]
