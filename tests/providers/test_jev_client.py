"""Jev adapter: real SDK request/response handling over a mock transport (no network)."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import SecretStr, ValidationError

from jev.budget.guard import BudgetExceededError, BudgetGuard, key_fingerprint
from jev.budget.pricing import UnknownModelError
from jev.providers.errors import ProviderError
from jev.providers.jev.live import LiveJevClient
from jev.providers.jev.types import ChoiceQ, JevRequest, NoulQ, ScoreQ
from tests.helpers import initialised_ledger

API_KEY = "ts-test-key"
RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "dept": {
            "type": "choice",
            "choice": "billing",
            "confidence": 0.81,
            "probabilities": {"billing": 0.88, "technical": 0.12},
        },
        "anger": {
            "type": "score",
            "score": 1.05,
            "confidence": 0.92,
            "legend": {"0": "Calm", "1": "Angry"},
            "probabilities": {"0": 0.0, "1": 1.0},
        },
        "urgent": {"type": "noul", "noul": 0.95},
    },
    "usage": {"input_tokens": 318, "output_tokens": 34},
}


class Recorder:
    def __init__(self, status: int = 200, body: dict[str, Any] | None = None) -> None:
        self.status = status
        self.body = RESPONSE if body is None else body
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(self.status, json=self.body)


def make_request(**overrides: Any) -> JevRequest:
    base: dict[str, Any] = {
        "state": {"ticket": "I was charged twice!"},
        "questions": {
            "dept": ChoiceQ(
                instructions="Which team?", criteria={"billing": None, "technical": "Bugs"}
            ),
            "anger": ScoreQ(instructions="How angry?", criteria=("Calm", "Angry")),
            "urgent": NoulQ(instructions="Is this urgent?"),
        },
        "purpose": "test.triage",
        "run_id": "run-1",
    }
    return JevRequest(**{**base, **overrides})


@pytest.fixture
def guard(tmp_path: Path) -> BudgetGuard:
    return BudgetGuard(initialised_ledger(tmp_path / "ledger.jsonl"), cap=Decimal("5.00"))


def client(guard: BudgetGuard, recorder: Recorder, model: str = "jev-latest") -> LiveJevClient:
    return LiveJevClient(
        api_key=SecretStr(API_KEY),
        model=model,
        guard=guard,
        transport=httpx2.MockTransport(recorder),
        max_retries=0,
    )


async def test_evaluate_maps_typed_answers_and_usage(guard: BudgetGuard) -> None:
    recorder = Recorder()

    result = await client(guard, recorder).evaluate(make_request())

    assert result.model == "jev-1.13.0"
    assert result.choices["dept"].choice == "billing"
    assert result.choices["dept"].probabilities == {"billing": 0.88, "technical": 0.12}
    assert result.scores["anger"].score == 1.05
    assert result.nouls["urgent"].noul == 0.95
    assert result.nouls["urgent"].confidence == pytest.approx(0.9)  # |2p - 1|
    assert (result.usage.input_tokens, result.usage.output_tokens) == (318, 34)
    assert result.latency_ms >= 0


async def test_request_body_matches_the_documented_api(guard: BudgetGuard) -> None:
    recorder = Recorder()

    await client(guard, recorder).evaluate(make_request())

    request = recorder.requests[0]
    assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
    assert request.headers["authorization"] == f"Bearer {API_KEY}"
    body = json.loads(request.content)
    assert body["model"] == "jev-latest"
    assert body["state"] == {"ticket": "I was charged twice!"}
    assert body["questions"]["dept"] == {
        "type": "choice",
        "instructions": "Which team?",
        "criteria": {"billing": None, "technical": "Bugs"},
    }
    assert body["questions"]["anger"]["criteria"] == ["Calm", "Angry"]
    assert body["questions"]["urgent"] == {"type": "noul", "instructions": "Is this urgent?"}


async def test_actual_cost_is_committed_to_the_ledger(guard: BudgetGuard) -> None:
    await client(guard, Recorder()).evaluate(make_request())

    status = guard.status("typesafe", key_fingerprint(API_KEY))
    assert status.reserved == 0
    assert status.spent == Decimal(318) * Decimal("0.042") / Decimal(1_000_000)


async def test_missing_usage_keeps_the_pessimistic_estimate(guard: BudgetGuard) -> None:
    body = {**RESPONSE, "usage": {"input_tokens": None, "output_tokens": None}}

    await client(guard, Recorder(body=body)).evaluate(make_request())

    assert guard.status("typesafe", key_fingerprint(API_KEY)).spent > 0


async def test_over_budget_call_is_never_sent(tmp_path: Path) -> None:
    tiny = BudgetGuard(
        initialised_ledger(tmp_path / "l.jsonl"), cap=Decimal("0.000001"), margin=Decimal("0")
    )
    recorder = Recorder()

    with pytest.raises(BudgetExceededError):
        await client(tiny, recorder).evaluate(make_request())

    assert recorder.requests == []


@pytest.mark.parametrize("status", [401, 422, 429, 500])
async def test_api_errors_become_provider_errors_and_keep_the_estimate(
    guard: BudgetGuard, status: int
) -> None:
    with pytest.raises(ProviderError) as info:
        await client(guard, Recorder(status=status, body={"error": "nope"})).evaluate(
            make_request()
        )

    assert API_KEY not in str(info.value)
    assert info.value.provider == "typesafe"
    budget = guard.status("typesafe", key_fingerprint(API_KEY))
    assert budget.reserved == 0 and budget.spent > 0  # may have been billed


def test_unknown_model_is_refused_up_front(guard: BudgetGuard) -> None:
    with pytest.raises(UnknownModelError):
        client(guard, Recorder(), model="jev-99")


def test_choice_needs_between_one_and_255_options() -> None:
    with pytest.raises(ValidationError):
        ChoiceQ(instructions="Pick", criteria={})
    with pytest.raises(ValidationError):
        ChoiceQ(instructions="Pick", criteria={str(i): None for i in range(256)})


@pytest.mark.parametrize("levels", [("one",), tuple(str(i) for i in range(11))])
def test_score_needs_between_two_and_ten_levels(levels: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError):
        ScoreQ(instructions="Rate", criteria=levels)


def test_request_needs_at_least_one_question() -> None:
    with pytest.raises(ValidationError):
        make_request(questions={})


def test_payload_is_deterministic_for_replay_hashing() -> None:
    first = make_request().payload("jev-latest")
    reordered = make_request(
        questions=dict(reversed(list(make_request().questions.items()))), run_id="other-run"
    ).payload("jev-latest")

    assert json.dumps(first, sort_keys=True) == json.dumps(reordered, sort_keys=True)
    assert "run_id" not in first


async def test_client_can_be_closed(guard: BudgetGuard) -> None:
    await client(guard, Recorder()).aclose()


async def test_cancellation_closes_the_reservation_and_propagates(
    guard: BudgetGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    jev = client(guard, Recorder())

    async def cancelled(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.CancelledError

    monkeypatch.setattr(jev._client, "system_one", cancelled)

    with pytest.raises(asyncio.CancelledError):
        await jev.evaluate(make_request())

    budget = guard.status("typesafe", key_fingerprint(API_KEY))
    assert budget.reserved == 0 and budget.spent > 0


async def test_malformed_answer_closes_the_reservation_and_raises(guard: BudgetGuard) -> None:
    body = {**RESPONSE, "answers": {"dept": {"type": "choice", "choice": 1}}}

    with pytest.raises(ProviderError):
        await client(guard, Recorder(body=body)).evaluate(make_request())

    assert guard.status("typesafe", key_fingerprint(API_KEY)).reserved == 0
