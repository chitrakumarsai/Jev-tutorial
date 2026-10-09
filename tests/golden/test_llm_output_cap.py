"""Golden: the LLM baseline is never cut off by our own output cap (that would be unfair)."""

import json
from pathlib import Path

import pytest

from jev.scenarios.s1_reconciliation.llm_pipeline import MAX_OUTPUT_TOKENS
from tests.golden.test_jev_estimates import RECORDINGS


@pytest.mark.parametrize("path", RECORDINGS, ids=[p.stem for p in RECORDINGS])
def test_recorded_llm_answers_were_complete_with_room_to_spare(path: Path) -> None:
    calls = [c for c in json.loads(path.read_text())["calls"] if c["provider"] == "openai"]

    for call in calls:
        result = call["result"]
        assert result["error"] != "truncated", "the output cap cut the baseline off"
        # Reasoning output varies run to run; keep at least 2x headroom over what was used.
        assert result["usage"]["output_tokens"] * 2 <= MAX_OUTPUT_TOKENS
