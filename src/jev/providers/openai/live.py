"""Live OpenAI adapter: budget-guarded Structured Outputs via the Responses API."""

import asyncio
import json
from collections.abc import Callable
from decimal import Decimal
from time import perf_counter
from typing import Any, Literal, TypeVar

import httpx2
import openai
from openai import AsyncOpenAI
from openai.types.responses import ParsedResponse
from pydantic import BaseModel, SecretStr, ValidationError

from jev.budget.estimator import estimate_call_cost
from jev.budget.guard import BudgetGuard, key_fingerprint
from jev.budget.pricing import cost_usd, price_for
from jev.providers.errors import ProviderError
from jev.providers.openai.types import LlmRequest, LlmResult, LlmUsage

DEFAULT_MAX_RETRIES = 2
DEFAULT_TIMEOUT_S = 120.0

T = TypeVar("T", bound=BaseModel)
NoAnswer = Literal["unparseable", "truncated", "content_filter"]


class LiveOpenAIClient:
    def __init__(
        self,
        *,
        api_key: SecretStr,
        model: str,
        guard: BudgetGuard,
        transport: httpx2.AsyncBaseTransport | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        price_for(model)  # unknown model: refuse before anything else happens
        self._model = model
        self._guard = guard
        self._attempts = max_retries + 1
        key = api_key.get_secret_value().strip()
        self._key_fp = key_fingerprint(key)
        http_client = httpx2.AsyncClient(transport=transport) if transport else None
        self._client = AsyncOpenAI(
            api_key=key,
            max_retries=max_retries,
            timeout=timeout_s,
            http_client=http_client,
        )

    @property
    def key_fp(self) -> str:
        return self._key_fp

    def estimate(self, request: LlmRequest, schema: type[BaseModel]) -> Decimal:
        """Worst-case cost of one request, used for reservations and whole-run pre-flight."""
        return estimate_call_cost(
            self._model,
            input_chars=_input_chars(request, schema),
            max_output_tokens=request.max_output_tokens,
            attempts=self._attempts,
        )

    async def parse(self, request: LlmRequest, schema: type[T]) -> LlmResult[T]:
        estimate = self.estimate(request, schema)
        # Ledger I/O (file lock + fsync) runs off the event loop.
        reservation = await asyncio.to_thread(
            self._guard.reserve, "openai", self._key_fp, estimate, run_id=request.run_id
        )
        started = perf_counter()
        try:
            # The raw wrapper keeps status and usage even when the output won't parse
            # (truncated, filtered or malformed), so we can label it and record real cost.
            raw = await self._client.responses.with_raw_response.parse(
                model=self._model,
                instructions=request.instructions,
                input=request.input,
                text_format=schema,
                max_output_tokens=request.max_output_tokens,
                store=False,  # keep audit documents off OpenAI's stored responses
            )
            body: dict[str, Any] = json.loads(raw.text)
            usage = _usage(body.get("usage"))
            actual = (
                cost_usd(self._model, usage.input_tokens, usage.output_tokens) if usage else None
            )
        except BaseException as exc:
            # Anything after the reservation (API error, bad body, cancellation) may have been
            # billed: keep the pessimistic estimate so the reservation never stays open.
            await asyncio.to_thread(self._guard.commit, reservation, actual=None)
            if isinstance(exc, openai.OpenAIError | ValueError | TypeError):
                raise ProviderError(
                    "openai", f"OpenAI request failed ({type(exc).__name__})"
                ) from None
            raise
        await asyncio.to_thread(self._guard.commit, reservation, actual=actual)
        latency_ms = round((perf_counter() - started) * 1000)
        return _to_result(raw.parse, body, usage, schema, latency_ms)

    async def aclose(self) -> None:
        await self._client.close()


def _input_chars(request: LlmRequest, schema: type[BaseModel]) -> int:
    """The JSON schema sent for Structured Outputs is billed as input too."""
    schema_chars = len(json.dumps(schema.model_json_schema()))
    return len(request.instructions) + len(request.input) + schema_chars


def _to_result(
    parse_raw: Callable[[], ParsedResponse[T]],
    body: dict[str, Any],
    usage: LlmUsage | None,
    schema: type[T],
    latency_ms: int,
) -> LlmResult[T]:
    try:
        response = parse_raw()
    except ValidationError:
        return LlmResult[schema](  # type: ignore[valid-type]
            model=str(body.get("model", "")),
            latency_ms=latency_ms,
            usage=usage,
            parsed=None,
            error=_no_answer_reason(body),
        )
    refusals = [
        part.refusal
        for item in response.output
        if item.type == "message"
        for part in item.content
        if part.type == "refusal"
    ]
    return LlmResult[schema](  # type: ignore[valid-type]
        model=response.model,
        latency_ms=latency_ms,
        usage=usage,
        parsed=response.output_parsed,
        refusal=refusals[0] if refusals else None,
    )


def _no_answer_reason(body: dict[str, Any]) -> NoAnswer:
    details = body.get("incomplete_details") or {}
    reason = details.get("reason") if isinstance(details, dict) else None
    if reason == "max_output_tokens":
        return "truncated"
    if reason == "content_filter":
        return "content_filter"
    return "unparseable"


def _usage(raw: object) -> LlmUsage | None:
    if not isinstance(raw, dict):
        return None
    details = raw.get("output_tokens_details") or {}
    return LlmUsage(
        input_tokens=int(raw.get("input_tokens", 0)),
        output_tokens=int(raw.get("output_tokens", 0)),
        reasoning_tokens=int(details.get("reasoning_tokens", 0))
        if isinstance(details, dict)
        else 0,
    )
