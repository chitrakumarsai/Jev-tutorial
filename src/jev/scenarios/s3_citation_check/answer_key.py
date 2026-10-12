"""S3 answer key: per memo citation, whether its source supports the claim, and whether the
cited section is the one the quote comes from. Written by hand before any model run."""

from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jev.domain.findings import CitationVerdict
from jev.scenarios.s3_citation_check.documents import scenario_dir


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class S3KeyItem(_Frozen):
    id: str
    citation_id: str = Field(pattern=r"^C\d+$")
    verdict: CitationVerdict
    # Whether the cited section holds the quote. A wrong section is noted on the finding,
    # not a separate verdict (presenter decision 2026-10-12). None for a fabricated quote.
    section_correct: bool | None = None
    trap: bool = False  # one of the planted errors
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def _section_fits_verdict(self) -> Self:
        if (self.verdict == "fabricated") != (self.section_correct is None):
            raise ValueError(
                f"{self.id}: a fabricated quote has no section to judge; any other needs one"
            )
        return self


class S3Key(_Frozen):
    scenario_id: str
    version: int
    authored_at: str
    reviewed_at: str | None = None  # set when the presenter has approved the key
    items: tuple[S3KeyItem, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        for field in ("id", "citation_id"):
            values = [getattr(item, field) for item in self.items]
            if len(values) != len(set(values)):
                raise ValueError(f"Duplicate {field} in the S3 answer key")
        return self


def load_s3_key(data_dir: Path) -> S3Key:
    path = scenario_dir(data_dir) / "answer_key.json"
    return S3Key.model_validate_json(path.read_text(encoding="utf-8"))
