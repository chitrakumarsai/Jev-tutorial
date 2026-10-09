"""Shared test helpers."""

from pathlib import Path

from jev.budget.ledger import Ledger


def initialised_ledger(path: Path) -> Ledger:
    """Ledgers are never auto-created (ADR 0002), so tests create one explicitly."""
    ledger = Ledger(path)
    ledger.initialise()
    return ledger
