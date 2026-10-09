"""Spend per provider, identified by key fingerprint only (never the key)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from jev.api.deps import get_settings
from jev.api.models import BudgetReport, BudgetRow, error_responses
from jev.api.schemas import Envelope
from jev.budget.guard import BudgetGuard, key_fingerprint
from jev.budget.ledger import Ledger, Provider
from jev.config import Settings

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get(
    "", summary="Spend per provider (key fingerprints only)", responses=error_responses(409)
)
def budget(settings: Annotated[Settings, Depends(get_settings)]) -> Envelope[BudgetReport]:
    initialised = settings.ledger_path.is_file()
    guard = BudgetGuard(Ledger(settings.ledger_path), cap=settings.budget_cap_usd)
    keys: dict[Provider, Any] = {
        "openai": settings.openai_api_key,
        "typesafe": settings.typesafe_api_key,
    }
    rows = [_row(guard, settings, provider, key, initialised) for provider, key in keys.items()]
    return Envelope.ok(BudgetReport(ledger_initialised=initialised, providers=rows))


def _row(
    guard: BudgetGuard, settings: Settings, provider: Provider, key: Any, initialised: bool
) -> BudgetRow:
    spent = reserved = remaining = None
    if key is not None and initialised:
        status = guard.status(provider, key_fingerprint(key.get_secret_value()))
        spent, reserved, remaining = str(status.spent), str(status.reserved), str(status.remaining)
    return BudgetRow(
        provider=provider,
        cap=str(settings.budget_cap_usd),
        key_configured=key is not None,
        spent=spent,
        reserved=reserved,
        remaining=remaining,
    )
