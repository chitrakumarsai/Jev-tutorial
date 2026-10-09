"""OpenAI adapter: real SDK request/response handling over a mock transport (no network)."""

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel, SecretStr

from jev.budget.guard import BudgetExceededError, BudgetGuard, key_fingerprint
from jev.budget.pricing import UnknownModelError
from jev.providers.errors import ProviderError
from jev.providers.openai.live import LiveOpenAIClient
from jev.providers.openai.types import LlmRequest
from tests.helpers import initialised_ledger

API_KEY = "sk-test-key"


class Answer(BaseModel):
    total: str


def message(content: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "resp_1",
        "object": "response",
        "created_at": 0,
        "model": "gpt-6-luna-2026-09-01",
        "status": "completed",
        "output": [
            {
                "type": "message",
                "id": "msg_1",
                "status": "completed",
                "role": "assistant",
                "content": [content],
            }
        ],
        "usage": {
            "input_tokens": 1_000,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 400,
            "output_tokens_details": {"reasoning_tokens": 100},
            "total_tokens": 1_400,
        },
        "parallel_tool_calls": False,
        "tool_choice": "auto",
        "tools": [],
    }


TEXT_OK = {"type": "output_text", "text": json.dumps({"total": "98510.71"}), "annotations": []}


class Recorder:
    def __init__(self, status: int = 200, body: dict[str, Any] | None = None) -> None:
        self.status = status
        self.body = message(TEXT_OK) if body is None else body
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(self.status, json=self.body)


@pytest.fixture
def guard(tmp_path: Path) -> BudgetGuard:
    return BudgetGuard(initialised_ledger(tmp_path / "ledger.jsonl"), cap=Decimal("5.00"))


def client(guard: BudgetGuard, recorder: Recorder, model: str = "gpt-6-luna") -> LiveOpenAIClient:
    return LiveOpenAIClient(
        api_key=SecretStr(API_KEY),
        model=model,
        guard=guard,
        transport=httpx2.MockTransport(recorder),
        max_retries=0,
    )


def request(**overrides: Any) -> LlmRequest:
    base: dict[str, Any] = {
        "instructions": "You are an auditor.",
        "input": "Contract and invoices...",
        "purpose": "s1.llm",
        "run_id": "run-1",
        "max_output_tokens": 4_000,
    }
    return LlmRequest(**{**base, **overrides})


async def test_parse_returns_structured_output_and_usage(guard: BudgetGuard) -> None:
    result = await client(guard, Recorder()).parse(request(), Answer)

    assert result.parsed == Answer(total="98510.71")
    assert result.refusal is None
    assert result.model == "gpt-6-luna-2026-09-01"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (1_000, 400)
    assert result.usage.reasoning_tokens == 100
    assert result.latency_ms >= 0


async def test_request_keeps_data_off_openai_and_caps_output(guard: BudgetGuard) -> None:
    recorder = Recorder()

    await client(guard, recorder).parse(request(), Answer)

    sent = recorder.requests[0]
    assert str(sent.url) == "https://api.openai.com/v1/responses"
    body = json.loads(sent.content)
    assert body["store"] is False
    assert body["model"] == "gpt-6-luna"
    assert body["max_output_tokens"] == 4_000
    assert body["instructions"] == "You are an auditor."
    assert body["text"]["format"]["type"] == "json_schema"


async def test_actual_cost_is_committed(guard: BudgetGuard) -> None:
    await client(guard, Recorder()).parse(request(), Answer)

    status = guard.status("openai", key_fingerprint(API_KEY))
    # 1,000 in x $0.10/M + 400 out x $0.50/M (reasoning tokens are part of output)
    assert status.spent == Decimal("0.0003")
    assert status.reserved == 0


async def test_refusal_is_a_scored_no_answer_not_a_crash(guard: BudgetGuard) -> None:
    body = message({"type": "refusal", "refusal": "I can't help with that."})

    result = await client(guard, Recorder(body=body)).parse(request(), Answer)

    assert result.parsed is None
    assert result.refusal == "I can't help with that."


async def test_unparseable_output_is_a_scored_no_answer(guard: BudgetGuard) -> None:
    body = message({"type": "output_text", "text": "not json at all", "annotations": []})

    result = await client(guard, Recorder(body=body)).parse(request(), Answer)

    assert result.parsed is None
    assert result.error == "unparseable"
    assert guard.status("openai", key_fingerprint(API_KEY)).spent > 0


async def test_over_budget_call_is_never_sent(tmp_path: Path) -> None:
    tiny = BudgetGuard(
        initialised_ledger(tmp_path / "l.jsonl"), cap=Decimal("0.000001"), margin=Decimal("0")
    )
    recorder = Recorder()

    with pytest.raises(BudgetExceededError):
        await client(tiny, recorder).parse(request(), Answer)

    assert recorder.requests == []


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_api_errors_become_provider_errors(guard: BudgetGuard, status: int) -> None:
    recorder = Recorder(status=status, body={"error": {"message": "nope", "type": "x"}})

    with pytest.raises(ProviderError) as info:
        await client(guard, recorder).parse(request(), Answer)

    assert API_KEY not in str(info.value)
    assert info.value.provider == "openai"
    assert guard.status("openai", key_fingerprint(API_KEY)).spent > 0


def test_unknown_model_is_refused_up_front(guard: BudgetGuard) -> None:
    with pytest.raises(UnknownModelError):
        client(guard, Recorder(), model="gpt-9-hyper")


def test_output_cap_must_be_positive() -> None:
    with pytest.raises(ValueError):
        request(max_output_tokens=0)


def test_payload_is_deterministic_and_excludes_run_id() -> None:
    first = request().payload("gpt-6-luna", Answer)
    second = request(run_id="another").payload("gpt-6-luna", Answer)

    assert first == second
    assert "run_id" not in json.dumps(first)
    assert first["schema"] == Answer.model_json_schema()


def incomplete(text: str, reason: str) -> dict[str, Any]:
    body = message({"type": "output_text", "text": text, "annotations": []})
    return {**body, "status": "incomplete", "incomplete_details": {"reason": reason}}


@pytest.mark.parametrize(
    ("body", "error"),
    [
        (incomplete('{"total": "98', "max_output_tokens"), "truncated"),
        (incomplete("", "content_filter"), "content_filter"),
    ],
)
async def test_truncated_or_filtered_output_is_labelled_and_real_cost_recorded(
    guard: BudgetGuard, body: dict[str, Any], error: str
) -> None:
    result = await client(guard, Recorder(body=body)).parse(request(), Answer)

    assert result.parsed is None
    assert result.error == error
    assert result.usage is not None and result.usage.output_tokens == 400
    assert guard.status("openai", key_fingerprint(API_KEY)).spent == Decimal("0.0003")


async def test_missing_usage_keeps_the_estimate(guard: BudgetGuard) -> None:
    body = {**message(TEXT_OK), "usage": None}

    result = await client(guard, Recorder(body=body)).parse(request(), Answer)

    assert result.usage is None
    assert guard.status("openai", key_fingerprint(API_KEY)).spent > Decimal("0.0003")


async def test_client_can_be_closed(guard: BudgetGuard) -> None:
    await client(guard, Recorder()).aclose()


async def test_non_json_body_closes_the_reservation_and_raises(guard: BudgetGuard) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"<html>proxy error</html>")

    llm = LiveOpenAIClient(
        api_key=SecretStr(API_KEY),
        model="gpt-6-luna",
        guard=guard,
        transport=httpx2.MockTransport(handler),
        max_retries=0,
    )

    with pytest.raises(ProviderError):
        await llm.parse(request(), Answer)

    status = guard.status("openai", key_fingerprint(API_KEY))
    assert status.reserved == 0 and status.spent > 0


async def test_cancellation_closes_the_reservation_and_propagates(
    guard: BudgetGuard, monkeypatch: pytest.MonkeyPatch
) -> None:
    llm = client(guard, Recorder())

    async def cancelled(*args: Any, **kwargs: Any) -> Any:
        raise asyncio.CancelledError

    monkeypatch.setattr(llm._client.responses.with_raw_response, "parse", cancelled)

    with pytest.raises(asyncio.CancelledError):
        await llm.parse(request(), Answer)

    assert guard.status("openai", key_fingerprint(API_KEY)).reserved == 0


async def test_key_whitespace_does_not_create_a_second_budget(guard: BudgetGuard) -> None:
    llm = LiveOpenAIClient(
        api_key=SecretStr(f"  {API_KEY}\n"),
        model="gpt-6-luna",
        guard=guard,
        transport=httpx2.MockTransport(Recorder()),
        max_retries=0,
    )

    await llm.parse(request(), Answer)

    assert guard.status("openai", key_fingerprint(API_KEY)).spent == Decimal("0.0003")
