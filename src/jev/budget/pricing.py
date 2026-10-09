"""Published model prices in USD per million tokens. Verified 2026-10-09.

Only models listed here may run live: an unknown model's cost can't be estimated,
so the budget guard refuses it.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType

PRICES_VERIFIED_ON = "2026-10-09"
_PER_MILLION = Decimal(1_000_000)


class UnknownModelError(ValueError):
    """The model has no verified price, so live calls to it are not allowed."""


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: Decimal
    output_per_mtok: Decimal


_JEV = ModelPrice(Decimal("0.042"), Decimal("0"))  # TypeSafe bills input only

PRICES: Mapping[str, ModelPrice] = MappingProxyType(
    {
        # OpenAI (developers.openai.com/api/docs/models)
        "gpt-6-luna": ModelPrice(Decimal("0.10"), Decimal("0.50")),
        "gpt-6.1-sol": ModelPrice(Decimal("2.00"), Decimal("10.00")),
        "gpt-6-astra": ModelPrice(Decimal("10.00"), Decimal("50.00")),
        # TypeSafe Jev (docs.typesafe.ai/models)
        "jev-latest": _JEV,
        "jev-1.13.0": _JEV,
    }
)


def price_for(model: str) -> ModelPrice:
    try:
        return PRICES[model]
    except KeyError:
        raise UnknownModelError(
            f"No verified price for model {model!r}; live calls to it are refused."
        ) from None


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> Decimal:
    """Exact cost of one call (not rounded; the ledger keeps sub-cent precision)."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("Token counts cannot be negative")
    price = price_for(model)
    return (
        Decimal(input_tokens) * price.input_per_mtok
        + Decimal(output_tokens) * price.output_per_mtok
    ) / _PER_MILLION
