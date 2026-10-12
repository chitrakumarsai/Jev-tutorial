"""D6: one approved live call drafts the S3 audit memo; nothing is sent without RECORD-style
confirmation, and every quote is checked against the S1 documents."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from jev.providers.openai.types import LlmRequest, LlmResult, LlmUsage
from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s3_citation_check.memo_draft import (
    CONFIRM_WORD,
    MemoCitation,
    MemoDraft,
    check_quotes,
    draft_memo,
    draft_request,
    save_draft,
)
from tests.s1.facts import DATA

DOCS = load_s1_documents(DATA)
REAL = "the volume discount applies to line-haul charges"


def a_draft(quote: str = "") -> MemoDraft:
    msa = DOCS.get("msa").text
    real_quote = quote or " ".join(msa.split("\n")[40].split()[:10])
    return MemoDraft(
        title="Northwind freight billing review",
        body="We reviewed 12 invoices [C1].",
        citations=[
            MemoCitation(id="C1", claim="A claim.", quote=real_quote, doc_id="msa", section="§4")
        ],
    )


class FakeLlm:
    key_fp = "fp"

    def __init__(self, draft: MemoDraft | None) -> None:
        self.draft, self.requests, self.closed = draft, [], False
        self.loops: dict[str, int] = {}

    def estimate(self, request: LlmRequest, schema: type[Any]) -> Decimal:
        return Decimal("0.0200")

    async def parse(self, request: LlmRequest, schema: type[Any]) -> LlmResult[Any]:
        self.loops["parse"] = id(asyncio.get_running_loop())
        self.requests.append(request)
        return LlmResult[schema](  # type: ignore[valid-type]
            model="gpt-6-luna",
            latency_ms=9_000,
            usage=LlmUsage(input_tokens=7_000, output_tokens=2_000),
            parsed=self.draft,
        )

    async def aclose(self) -> None:
        self.loops["aclose"] = id(asyncio.get_running_loop())
        self.closed = True


class FakeGuard:
    def __init__(self) -> None:
        self.preflights: list[Any] = []

    def preflight(self, estimates: Any) -> None:  # matches BudgetGuard.preflight
        self.preflights.append(estimates)


def run(tmp_path: Path, llm: FakeLlm, answer: str) -> tuple[int, FakeGuard]:
    guard = FakeGuard()
    code = draft_memo(
        DOCS,
        tmp_path,
        llm_factory=lambda: llm,
        guard=guard,
        input_fn=lambda prompt: answer,
    )
    return code, guard


def test_the_prompt_asks_for_a_cited_memo_from_the_s1_documents_as_untrusted_data() -> None:
    request = draft_request(DOCS)

    assert "untrusted data" in request.instructions
    assert "verbatim" in request.instructions and "[C1]" in request.instructions
    assert request.input.count("<document id=") == len(DOCS.documents)


def test_nothing_is_sent_without_the_confirmation_word(tmp_path: Path) -> None:
    llm = FakeLlm(a_draft())

    code, guard = run(tmp_path, llm, "yes")

    assert code == 1
    assert llm.requests == [] and llm.closed
    assert len(guard.preflights) == 1  # the estimate was checked before asking
    assert not (tmp_path / "memo_draft.json").exists()


def test_a_confirmed_draft_is_saved_for_the_presenter_to_edit(tmp_path: Path) -> None:
    llm = FakeLlm(a_draft())

    code, _ = run(tmp_path, llm, CONFIRM_WORD)

    assert code == 0 and llm.closed
    saved = json.loads((tmp_path / "memo_draft.json").read_text(encoding="utf-8"))
    assert saved["citations"][0]["id"] == "C1"
    assert "[C1]" in (tmp_path / "memo.md").read_text(encoding="utf-8")


def test_no_usable_answer_saves_nothing(tmp_path: Path) -> None:
    code, _ = run(tmp_path, FakeLlm(None), CONFIRM_WORD)

    assert code == 1
    assert not (tmp_path / "memo_draft.json").exists()


def test_quotes_not_found_in_the_documents_are_reported() -> None:
    assert check_quotes(a_draft(), DOCS) == []
    problems = check_quotes(a_draft(quote="words that appear in none of the documents"), DOCS)
    assert problems and "C1" in problems[0]


def test_saving_writes_json_and_a_readable_markdown_memo(tmp_path: Path) -> None:
    save_draft(a_draft(), tmp_path)

    memo = (tmp_path / "memo.md").read_text(encoding="utf-8")
    assert memo.startswith("# Northwind freight billing review")
    assert "C1" in memo and "msa" in memo


@pytest.mark.parametrize("bad", ["c1", "C", "X1"])
def test_citation_ids_are_c_numbers(bad: str) -> None:
    with pytest.raises(ValueError):
        MemoCitation(id=bad, claim="c", quote="q", doc_id="msa", section="§1")


def test_the_cli_refuses_while_live_mode_is_off(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from jev.cli import main

    monkeypatch.setenv("LIVE_ENABLED", "false")

    code = main(["draft-memo", "--data-dir", str(DATA), "--out-dir", str(tmp_path)])

    assert code == 1
    assert "Refused" in capsys.readouterr().err
    assert not (tmp_path / "memo_draft.json").exists()


def test_the_call_and_closing_its_connections_share_one_event_loop(tmp_path: Path) -> None:
    # Regression: closing in a second asyncio.run raised "Event loop is closed" after a
    # paid call, so the draft was lost.
    llm = FakeLlm(a_draft())

    code, _ = run(tmp_path, llm, CONFIRM_WORD)

    assert code == 0
    assert llm.loops["parse"] == llm.loops["aclose"]
