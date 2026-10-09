"""Spend per provider, identified by key fingerprint only (never the key)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from jev.api.deps import get_settings
from jev.api.schemas import Envelope
from jev.budget.guard import BudgetGuard, key_fingerprint
from jev.budget.ledger import Ledger, Provider
from jev.config import Settings

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("")
def budget(settings: Annotated[Settings, Depends(get_settings)]) -> Envelope[dict[str, Any]]:
    initialised = settings.ledger_path.is_file()
    guard = BudgetGuard(Ledger(settings.ledger_path), cap=settings.budget_cap_usd)
    keys: dict[Provider, Any] = {
        "openai": settings.openai_api_key,
        "typesafe": settings.typesafe_api_key,
    }
    providers = []
    for provider, key in keys.items():
        row: dict[str, Any] = {
            "provider": provider,
            "cap": str(settings.budget_cap_usd),
            "key_configured": key is not None,
            "spent": None,
            "reserved": None,
            "remaining": None,
        }
        if key is not None and initialised:
            status = guard.status(provider, key_fingerprint(key.get_secret_value()))
            row |= {
                "spent": str(status.spent),
                "reserved": str(status.reserved),
                "remaining": str(status.remaining),
            }
        providers.append(row)
    return Envelope.ok({"ledger_initialised": initialised, "providers": providers})
