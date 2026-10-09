"""Live Jev adapter: budget-guarded calls through the official typesafe-sdk."""

import asyncio
import json
from decimal import Decimal
from time import perf_counter

import httpx2
from pydantic import SecretStr
from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    Noul,
    RetryPolicy,
    Score,
    SystemOneResponse,
    TypeSafeAPIError,
    TypeSafeError,
)

from jev.budget.estimator import estimate_call_cost
from jev.budget.guard import BudgetGuard, key_fingerprint
from jev.budget.pricing import cost_usd, price_for
from jev.providers.errors import ProviderError, safe_failure
from jev.providers.jev.types import (
    ChoiceA,
    ChoiceQ,
    JevRequest,
    JevResult,
    NoulA,
    NoulQ,
    Question,
    ScoreA,
    Usage,
)

DEFAULT_MAX_RETRIES = 2
DEFAULT_TIMEOUT_S = 30.0

SdkQuestion = Choice | Score | Noul


def _to_sdk(question: Question) -> SdkQuestion:
    if isinstance(question, ChoiceQ):
        return Choice(instructions=question.instructions, criteria=question.criteria)
    if isinstance(question, NoulQ):
        criteria = question.criteria.model_dump(exclude_none=True) if question.criteria else None
        return Noul(instructions=question.instructions, criteria=criteria or None)  # type: ignore[arg-type]
    return Score(instructions=question.instructions, criteria=list(question.criteria))


def _pessimistic_input_chars(request: JevRequest, model: str) -> int:
    """Assume the state is billed once per question until real usage proves otherwise."""
    state_chars = len(json.dumps(request.state))
    return state_chars * len(request.questions) + len(json.dumps(request.payload(model)))


class LiveJevClient:
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
        self._client = AsyncTypeSafeClient(
            api_key=key,
            model=model,
            retry=RetryPolicy(max_retries=max_retries),
            timeout=timeout_s,
            transport=transport,
        )

    @property
    def key_fp(self) -> str:
        return self._key_fp

    def estimate(self, request: JevRequest) -> Decimal:
        """Worst-case cost of one request, used for reservations and whole-run pre-flight."""
        return estimate_call_cost(
            self._model,
            input_chars=_pessimistic_input_chars(request, self._model),
            max_output_tokens=0,
            attempts=self._attempts,
        )

    async def evaluate(self, request: JevRequest) -> JevResult:
        estimate = self.estimate(request)
        # Ledger I/O (file lock + fsync) runs off the event loop.
        reservation = await asyncio.to_thread(
            self._guard.reserve, "typesafe", self._key_fp, estimate, run_id=request.run_id
        )
        started = perf_counter()
        try:
            response = await self._client.system_one(
                state=request.state,  # type: ignore[arg-type]
                questions={key: _to_sdk(q) for key, q in request.questions.items()},
                model=self._model,
            )
            latency_ms = round((perf_counter() - started) * 1000)
            actual = self._actual_cost(response)
            result = _to_result(response, latency_ms)
        except BaseException as exc:
            # Anything after the reservation (SDK error, bad response, cancellation) may have
            # been billed: keep the pessimistic estimate so the reservation never stays open.
            await asyncio.to_thread(self._guard.commit, reservation, actual=None)
            if isinstance(exc, TypeSafeError | ValueError | TypeError):
                raise ProviderError("typesafe", f"Jev request failed ({_failure(exc)})") from None
            raise
        await asyncio.to_thread(self._guard.commit, reservation, actual=actual)
        return result

    def _actual_cost(self, response: SystemOneResponse) -> Decimal | None:
        """Priced at the configured model, never at what the response claims to be."""
        tokens = response.usage.input_tokens
        return None if tokens is None else cost_usd(self._model, max(tokens, 0), 0)

    async def aclose(self) -> None:
        await self._client.aclose()


def _failure(exc: BaseException) -> str:
    if isinstance(exc, TypeSafeAPIError):
        return safe_failure(exc, status=exc.status, request_id=exc.request_id)
    return safe_failure(exc)


def _to_result(response: SystemOneResponse, latency_ms: int) -> JevResult:
    return JevResult(
        model=response.model,
        latency_ms=latency_ms,
        choices={
            k: ChoiceA(
                choice=a.choice, probabilities=dict(a.probabilities), confidence=a.confidence
            )
            for k, a in response.choices.items()
        },
        scores={
            k: ScoreA(
                score=a.score,
                probabilities={str(level): p for level, p in a.probabilities.items()},
                confidence=a.confidence,
            )
            for k, a in response.scores.items()
        },
        nouls={k: NoulA(noul=a.noul) for k, a in response.nouls.items()},
        usage=Usage(
            input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens
        ),
    )
