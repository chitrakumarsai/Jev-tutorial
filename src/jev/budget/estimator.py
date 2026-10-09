"""Pessimistic pre-flight cost estimates: better to refuse early than overspend."""

from decimal import Decimal

from jev.budget.pricing import cost_usd

# ~3 chars per token for English plus 20% headroom => tokens = ceil(chars * 2 / 5).
_TOKENS_PER_CHAR_NUM, _TOKENS_PER_CHAR_DEN = 2, 5


def _tokens_for_chars(chars: int) -> int:
    return -(-chars * _TOKENS_PER_CHAR_NUM // _TOKENS_PER_CHAR_DEN)


def estimate_tokens(text: str) -> int:
    return _tokens_for_chars(len(text))


def estimate_call_cost(
    model: str, *, input_chars: int, max_output_tokens: int, attempts: int
) -> Decimal:
    """Worst case: the full output cap is used on every attempt (retries are billed too)."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    return cost_usd(model, _tokens_for_chars(input_chars), max_output_tokens) * attempts
