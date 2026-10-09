"""Golden: the pre-flight Jev estimate covers the input actually billed in every recording."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr

from jev.budget.guard import BudgetGuard
from jev.budget.ledger import Ledger
from jev.budget.pricing import cost_usd
from jev.providers.jev.live import LiveJevClient
from jev.replay.hashing import request_hash
from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s1_reconciliation.jev_pipeline import JevS1Pipeline
from tests.s1.facts import DATA

RECORDINGS = sorted((DATA / "replays" / "s1_reconciliation").glob("*.json"))


@pytest.mark.parametrize("path", RECORDINGS, ids=[p.stem for p in RECORDINGS])
def test_estimates_cover_billed_input_for_every_recorded_jev_call(
    path: Path, tmp_path: Path
) -> None:
    recording = json.loads(path.read_text())
    billed = {
        call["request_hash"]: call["result"]["usage"]["input_tokens"]
        for call in recording["calls"]
        if call["provider"] == "typesafe"
    }
    model = recording["jev_model"]
    client = LiveJevClient(
        api_key=SecretStr("ts-test"),
        model=model,
        guard=BudgetGuard(Ledger(tmp_path / "l.jsonl"), cap=Decimal("5")),
        max_retries=0,
    )
    pipeline = JevS1Pipeline(load_s1_documents(DATA), review_threshold=0.8, run_id="golden")

    checked = 0
    for request in pipeline.requests():
        tokens = billed[request_hash(request.payload(model))]  # KeyError => stale recording
        assert client.estimate(request) >= cost_usd(model, tokens, 0), request.purpose
        assert client.estimate(request) <= 2 * cost_usd(model, tokens, 0), request.purpose
        checked += 1
    assert checked == len(billed)


def test_there_is_at_least_one_committed_recording_to_check() -> None:
    assert RECORDINGS, "no committed S1 recordings: the estimate check above would be vacuous"


def test_estimates_keep_headroom_for_token_dense_payloads(tmp_path: Path) -> None:
    from jev.providers.jev.types import ChoiceQ, JevRequest

    digits = " ".join(f"INV-{n:06d} ${n * 7:,}.{n % 100:02d}" for n in range(400))
    request = JevRequest(
        purpose="dense",
        run_id="golden",
        state={"invoice": digits},
        questions={"q": ChoiceQ(instructions="Which one?", criteria={"a": None, "b": None})},
    )
    client = LiveJevClient(
        api_key=SecretStr("ts-test"),
        model="jev-latest",
        guard=BudgetGuard(Ledger(tmp_path / "l.jsonl"), cap=Decimal("5")),
        max_retries=0,
    )
    payload_chars = len(json.dumps(request.payload("jev-latest")))

    # Allow 0.5 tokens per char (observed: 0.37-0.47) on top of the fixed overhead.
    assert client.estimate(request) >= cost_usd("jev-latest", payload_chars // 2, 0)
