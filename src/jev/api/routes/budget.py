"""Spend per provider, identified by key fingerprint only (never the key)."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends

from jev.api.deps import get_settings
from jev.api.models import BudgetReport, BudgetRow, error_responses
from jev.api.schemas import Envelope
from jev.budget.report import ProviderBudget, budget_report
from jev.config import Settings

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get(
    "", summary="Spend per provider (key fingerprints only)", responses=error_responses(409)
)
def budget(settings: Annotated[Settings, Depends(get_settings)]) -> Envelope[BudgetReport]:
    initialised, rows = budget_report(settings)
    return Envelope.ok(
        BudgetReport(ledger_initialised=initialised, providers=[_row(r) for r in rows])
    )


def _row(row: ProviderBudget) -> BudgetRow:
    def text(amount: Decimal | None) -> str | None:
        return None if amount is None else str(amount)

    return BudgetRow(
        provider=row.provider,
        cap=str(row.cap),
        key_configured=row.key_configured,
        spent=text(row.spent),
        reserved=text(row.reserved),
        remaining=text(row.remaining),
    )
