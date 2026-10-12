"""S3 inputs: the S1 documents (the memo's sources) and the planted memo itself."""

from pathlib import Path

from jev.scenarios.s3_citation_check.memo_draft import MemoDraft

SCENARIO_ID = "s3_citation_check"


def scenario_dir(data_dir: Path) -> Path:
    return data_dir / "scenarios" / SCENARIO_ID


def load_memo(data_dir: Path) -> MemoDraft:
    """The memo with the presenter's planted errors (memo_draft.json is the LLM original)."""
    return MemoDraft.model_validate_json((scenario_dir(data_dir) / "memo.json").read_text("utf-8"))
