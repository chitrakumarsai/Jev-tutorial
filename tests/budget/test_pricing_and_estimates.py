from decimal import Decimal

import pytest

from jev.budget.estimator import estimate_call_cost, estimate_tokens
from jev.budget.pricing import PRICES, UnknownModelError, cost_usd, price_for


def test_verified_prices() -> None:
    assert price_for("gpt-6-luna").input_per_mtok == Decimal("0.10")
    assert price_for("gpt-6-luna").output_per_mtok == Decimal("0.50")
    assert price_for("jev-latest").input_per_mtok == Decimal("0.042")
    assert price_for("jev-latest").output_per_mtok == Decimal("0")
    assert price_for("jev-1.13.0") == price_for("jev-latest")


def test_unknown_model_is_refused_because_its_cost_cannot_be_estimated() -> None:
    with pytest.raises(UnknownModelError, match="gpt-9-hyper"):
        price_for("gpt-9-hyper")


def test_cost_is_input_plus_output_per_million_tokens() -> None:
    # 1M input at $0.10 + 1M output at $0.50
    assert cost_usd("gpt-6-luna", 1_000_000, 1_000_000) == Decimal("0.60")
    # Jev output is free
    assert cost_usd("jev-latest", 500_000, 999_999) == Decimal("0.021")


def test_cost_rejects_negative_token_counts() -> None:
    with pytest.raises(ValueError):
        cost_usd("gpt-6-luna", -1, 0)


def test_token_estimate_is_conservative() -> None:
    # chars / 3, plus 20% headroom, rounded up
    assert estimate_tokens("") == 0
    assert estimate_tokens("x" * 300) == 120
    assert estimate_tokens("x" * 301) == 121


def test_call_estimate_reserves_full_output_cap_for_every_attempt() -> None:
    estimate = estimate_call_cost(
        "gpt-6-luna", input_chars=3_000, max_output_tokens=4_000, attempts=3
    )
    one_attempt = cost_usd("gpt-6-luna", 1_200, 4_000)

    assert estimate == one_attempt * 3
    assert estimate > 0


def test_call_estimate_needs_at_least_one_attempt() -> None:
    with pytest.raises(ValueError):
        estimate_call_cost("gpt-6-luna", input_chars=10, max_output_tokens=10, attempts=0)


def test_every_priced_model_has_non_negative_prices() -> None:
    for model, price in PRICES.items():
        assert price.input_per_mtok >= 0 and price.output_per_mtok >= 0, model
