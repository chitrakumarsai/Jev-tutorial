"""Budget guard: refuses any reservation that would take a key past its cap (ADR 0002)."""

import hashlib
import threading
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from jev.budget.ledger import EntryKind, Ledger, LedgerEntry, LedgerSession, Provider
from jev.config import HARD_BUDGET_CAP_USD

DEFAULT_SAFETY_MARGIN = Decimal("0.25")
_FINGERPRINT_CHARS = 12


class BudgetExceededError(RuntimeError):
    """The call would take this API key past its spend cap; nothing was sent."""


def key_fingerprint(api_key: str) -> str:
    """Stable, non-reversible identifier for an API key (the key itself is never stored)."""
    return hashlib.sha256(api_key.strip().encode("utf-8")).hexdigest()[:_FINGERPRINT_CHARS]


@dataclass(frozen=True)
class Reservation:
    id: str
    provider: Provider
    key_fp: str
    amount: Decimal
    run_id: str


@dataclass(frozen=True)
class BudgetStatus:
    provider: Provider
    cap: Decimal
    margin: Decimal
    spent: Decimal
    reserved: Decimal

    @property
    def remaining(self) -> Decimal:
        return self.cap - self.margin - self.spent - self.reserved


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _status(
    session: LedgerSession, provider: Provider, key_fp: str, cap: Decimal, margin: Decimal
) -> BudgetStatus:
    mine = [e for e in session.entries if e.provider == provider and e.key_fp == key_fp]
    closed = {e.id for e in mine if e.kind in ("commit", "release")}
    spent = sum((e.amount for e in mine if e.kind in ("commit", "adjust")), Decimal("0"))
    reserved = sum(
        (e.amount for e in mine if e.kind == "reserve" and e.id not in closed), Decimal("0")
    )
    return BudgetStatus(provider, cap, margin, spent, reserved)


class BudgetGuard:
    def __init__(
        self, ledger: Ledger, *, cap: Decimal, margin: Decimal = DEFAULT_SAFETY_MARGIN
    ) -> None:
        if not Decimal("0") < cap <= HARD_BUDGET_CAP_USD:
            raise ValueError(f"cap must be in (0, {HARD_BUDGET_CAP_USD}]")
        if not Decimal("0") <= margin < cap:
            raise ValueError("margin must be >= 0 and below the cap")
        self._ledger = ledger
        self._cap = cap
        self._margin = margin
        self._lock = threading.Lock()  # in-process; the ledger file lock covers other processes

    def status(self, provider: Provider, key_fp: str) -> BudgetStatus:
        with self._lock, self._ledger.session() as session:
            return _status(session, provider, key_fp, self._cap, self._margin)

    def preflight(self, estimates: Mapping[tuple[Provider, str], Decimal]) -> None:
        """Check a whole run up front; raises BudgetExceededError and writes nothing."""
        with self._lock, self._ledger.session() as session:
            for (provider, key_fp), amount in estimates.items():
                status = _status(session, provider, key_fp, self._cap, self._margin)
                if amount > status.remaining:
                    raise BudgetExceededError(
                        f"{provider} run needs ~${amount} but only ${status.remaining} remains"
                    )

    def reserve(
        self, provider: Provider, key_fp: str, amount: Decimal, *, run_id: str
    ) -> Reservation:
        if amount <= 0:
            raise ValueError("A reservation must be positive")
        with self._lock, self._ledger.session() as session:
            status = _status(session, provider, key_fp, self._cap, self._margin)
            if amount > status.remaining:
                raise BudgetExceededError(
                    f"{provider} call needs ~${amount} but only ${status.remaining} remains "
                    f"of the ${self._cap} cap"
                )
            reservation = Reservation(uuid.uuid4().hex, provider, key_fp, amount, run_id)
            session.append(self._entry(reservation, "reserve", amount))
            return reservation

    def commit(self, reservation: Reservation, *, actual: Decimal | None) -> None:
        """Record what the call really cost; None keeps the (pessimistic) estimate."""
        if actual is not None and not (actual.is_finite() and actual >= 0):
            raise ValueError("Actual cost must be a finite, non-negative amount")
        self._close(reservation, "commit", reservation.amount if actual is None else actual)

    def release(self, reservation: Reservation) -> None:
        """The call was never sent, so nothing was spent."""
        self._close(reservation, "release", Decimal("0"))

    def adjust(self, provider: Provider, key_fp: str, amount: Decimal, *, note: str) -> None:
        """Record spend made outside this app. Only adds spend; it can never free budget."""
        if not (amount.is_finite() and amount > 0):
            raise ValueError("An adjustment must be a finite, positive amount")
        entry = LedgerEntry(
            _now(), provider, key_fp, "adjust", str(amount), uuid.uuid4().hex, note=note
        )
        with self._lock, self._ledger.session() as session:
            session.append(entry)

    def _close(self, reservation: Reservation, kind: EntryKind, amount: Decimal) -> None:
        with self._lock, self._ledger.session() as session:
            mine = [e for e in session.entries if e.id == reservation.id]
            if not any(
                e.kind == "reserve"
                and e.provider == reservation.provider
                and e.key_fp == reservation.key_fp
                for e in mine
            ):
                raise ValueError(f"There is no matching reservation {reservation.id}")
            if any(e.kind in ("commit", "release") for e in mine):
                raise ValueError(f"Reservation {reservation.id} is already closed")
            session.append(self._entry(reservation, kind, amount))

    @staticmethod
    def _entry(reservation: Reservation, kind: EntryKind, amount: Decimal) -> LedgerEntry:
        return LedgerEntry(
            ts=_now(),
            provider=reservation.provider,
            key_fp=reservation.key_fp,
            kind=kind,
            usd=str(amount),
            id=reservation.id,
            run_id=reservation.run_id,
        )
