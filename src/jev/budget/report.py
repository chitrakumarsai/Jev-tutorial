"""Spend per provider for people (CLI) and the UI (API). Read-only; never touches a key
beyond fingerprinting it to find its ledger lines."""

from dataclasses import dataclass
from decimal import Decimal

from pydantic import SecretStr

from jev.budget.guard import BudgetGuard, key_fingerprint
from jev.budget.ledger import Ledger, Provider
from jev.config import Settings


@dataclass(frozen=True)
class ProviderBudget:
    provider: Provider
    cap: Decimal
    key_configured: bool
    spent: Decimal | None  # None when no key is configured or no ledger exists yet
    reserved: Decimal | None
    remaining: Decimal | None


def _configured(key: SecretStr | None) -> bool:
    return key is not None and bool(key.get_secret_value().strip())


def budget_report(settings: Settings) -> tuple[bool, list[ProviderBudget]]:
    """(ledger initialised, one row per provider)."""
    initialised = settings.ledger_path.is_file()
    guard = BudgetGuard(Ledger(settings.ledger_path), cap=settings.budget_cap_usd)
    keys: dict[Provider, SecretStr | None] = {
        "openai": settings.openai_api_key,
        "typesafe": settings.typesafe_api_key,
    }
    rows = []
    for provider, key in keys.items():
        configured = _configured(key)
        amounts: tuple[Decimal | None, Decimal | None, Decimal | None]
        if configured and initialised and key is not None:
            status = guard.status(provider, key_fingerprint(key.get_secret_value()))
            amounts = (status.spent, status.reserved, status.remaining)
        else:
            amounts = (None, None, None)
        rows.append(ProviderBudget(provider, settings.budget_cap_usd, configured, *amounts))
    return initialised, rows
