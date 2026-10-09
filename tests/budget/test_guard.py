"""The budget guard enforces the hard $5-per-key cap before any call is made."""

import json
from decimal import Decimal
from pathlib import Path

import pytest

from jev.budget.guard import BudgetExceededError, BudgetGuard, Reservation, key_fingerprint
from jev.budget.ledger import Ledger, LedgerCorruptError, LedgerMissingError

KEY = key_fingerprint("sk-test-key")


@pytest.fixture
def ledger_path(tmp_path: Path) -> Path:
    path = tmp_path / "var" / "ledger.jsonl"
    Ledger(path).initialise()
    return path


def guard(path: Path, cap: str = "5.00", margin: str = "0.25") -> BudgetGuard:
    return BudgetGuard(Ledger(path), cap=Decimal(cap), margin=Decimal(margin))


def test_key_fingerprint_is_short_stable_and_not_the_key() -> None:
    fp = key_fingerprint("sk-test-key")

    assert fp == key_fingerprint("sk-test-key")
    assert len(fp) == 12
    assert "sk-test" not in fp
    assert fp != key_fingerprint("sk-other-key")


def test_fresh_ledger_has_full_budget(ledger_path: Path) -> None:
    status = guard(ledger_path).status("openai", KEY)

    assert status.spent == 0
    assert status.reserved == 0
    assert status.remaining == Decimal("4.75")  # cap minus safety margin


def test_reserve_then_commit_records_actual_cost(ledger_path: Path) -> None:
    g = guard(ledger_path)

    reservation = g.reserve("openai", KEY, Decimal("0.40"), run_id="r1")
    assert g.status("openai", KEY).reserved == Decimal("0.40")

    g.commit(reservation, actual=Decimal("0.003"))
    status = g.status("openai", KEY)
    assert status.reserved == 0
    assert status.spent == Decimal("0.003")


def test_commit_without_actual_keeps_the_estimate(ledger_path: Path) -> None:
    g = guard(ledger_path)
    reservation = g.reserve("typesafe", KEY, Decimal("0.01"), run_id="r1")

    g.commit(reservation, actual=None)

    assert g.status("typesafe", KEY).spent == Decimal("0.01")


def test_release_frees_a_reservation_for_a_call_never_sent(ledger_path: Path) -> None:
    g = guard(ledger_path)
    reservation = g.reserve("openai", KEY, Decimal("1.00"), run_id="r1")

    g.release(reservation)

    assert g.status("openai", KEY).reserved == 0
    assert g.status("openai", KEY).spent == 0


def test_reservation_that_would_cross_the_cap_is_refused(ledger_path: Path) -> None:
    g = guard(ledger_path)
    g.commit(g.reserve("openai", KEY, Decimal("4.00"), run_id="r1"), actual=Decimal("4.00"))

    with pytest.raises(BudgetExceededError, match="openai"):
        g.reserve("openai", KEY, Decimal("0.80"), run_id="r2")  # 4.80 > 4.75


def test_open_reservations_count_against_the_cap(ledger_path: Path) -> None:
    g = guard(ledger_path)
    g.reserve("openai", KEY, Decimal("3.00"), run_id="r1")

    with pytest.raises(BudgetExceededError):
        g.reserve("openai", KEY, Decimal("2.00"), run_id="r2")


def test_budgets_are_separate_per_provider_and_key(ledger_path: Path) -> None:
    g = guard(ledger_path)
    g.commit(g.reserve("openai", KEY, Decimal("4.70"), run_id="r1"), actual=None)

    g.reserve("typesafe", KEY, Decimal("4.70"), run_id="r2")
    g.reserve("openai", key_fingerprint("another-key"), Decimal("4.70"), run_id="r3")


def test_preflight_checks_the_whole_run_without_writing(ledger_path: Path) -> None:
    g = guard(ledger_path)
    g.commit(g.reserve("openai", KEY, Decimal("4.00"), run_id="r1"), actual=None)

    g.preflight({("typesafe", KEY): Decimal("0.01"), ("openai", KEY): Decimal("0.50")})
    with pytest.raises(BudgetExceededError):
        g.preflight({("openai", KEY): Decimal("0.76")})
    assert g.status("openai", KEY).reserved == 0


def test_spend_persists_across_guard_instances(ledger_path: Path) -> None:
    guard(ledger_path).commit(
        guard(ledger_path).reserve("openai", KEY, Decimal("1.00"), run_id="r1"), actual=None
    )

    assert guard(ledger_path).status("openai", KEY).spent == Decimal("1.00")


def test_ledger_never_contains_the_raw_key(ledger_path: Path) -> None:
    g = guard(ledger_path)
    g.commit(g.reserve("openai", KEY, Decimal("0.10"), run_id="r1"), actual=None)

    text = ledger_path.read_text()
    assert "sk-test-key" not in text
    assert KEY in text


def test_corrupt_ledger_fails_closed(ledger_path: Path) -> None:
    ledger_path.write_text('{"kind": "commit"\nnot json\n')

    with pytest.raises(LedgerCorruptError):
        guard(ledger_path).reserve("openai", KEY, Decimal("0.01"), run_id="r1")


def test_unknown_entry_kind_fails_closed(ledger_path: Path) -> None:
    entry = {
        "ts": "t",
        "provider": "openai",
        "key_fp": KEY,
        "kind": "refund",
        "usd": "-9",
        "id": "x",
    }
    ledger_path.write_text(json.dumps(entry) + "\n")

    with pytest.raises(LedgerCorruptError):
        guard(ledger_path).status("openai", KEY)


def test_manual_adjustment_counts_as_spend(ledger_path: Path) -> None:
    g = guard(ledger_path)

    g.adjust("openai", KEY, Decimal("0.42"), note="spent outside the app")

    assert g.status("openai", KEY).spent == Decimal("0.42")


@pytest.mark.parametrize("amount", ["0", "-1"])
def test_non_positive_reservations_are_rejected(ledger_path: Path, amount: str) -> None:
    with pytest.raises(ValueError):
        guard(ledger_path).reserve("openai", KEY, Decimal(amount), run_id="r1")


def test_double_commit_is_rejected(ledger_path: Path) -> None:
    g = guard(ledger_path)
    reservation = g.reserve("openai", KEY, Decimal("0.10"), run_id="r1")
    g.commit(reservation, actual=None)

    with pytest.raises(ValueError, match="already closed"):
        g.commit(reservation, actual=None)


@pytest.mark.parametrize(("cap", "margin"), [("5.01", "0.25"), ("1.00", "-0.01"), ("1.00", "1.00")])
def test_invalid_cap_or_margin_is_rejected(ledger_path: Path, cap: str, margin: str) -> None:
    with pytest.raises(ValueError):
        guard(ledger_path, cap=cap, margin=margin)


# --- Security review fixes (H1, H2, L6, L9, L10) -------------------------------------------


@pytest.mark.parametrize("amount", ["-5", "0", "NaN", "Infinity"])
def test_adjust_only_adds_finite_positive_spend(ledger_path: Path, amount: str) -> None:
    with pytest.raises(ValueError):
        guard(ledger_path).adjust("openai", KEY, Decimal(amount), note="x")


@pytest.mark.parametrize("actual", ["-0.01", "NaN", "Infinity"])
def test_commit_rejects_negative_or_non_finite_cost(ledger_path: Path, actual: str) -> None:
    g = guard(ledger_path)
    reservation = g.reserve("openai", KEY, Decimal("0.10"), run_id="r1")

    with pytest.raises(ValueError):
        g.commit(reservation, actual=Decimal(actual))


@pytest.mark.parametrize("usd", ["-4.00", "NaN", "Infinity", "-0.01"])
def test_ledger_with_negative_or_non_finite_amounts_fails_closed(
    ledger_path: Path, usd: str
) -> None:
    entry = {
        "ts": "t",
        "provider": "openai",
        "key_fp": KEY,
        "kind": "adjust",
        "usd": usd,
        "id": "x",
    }
    ledger_path.write_text(json.dumps(entry) + "\n")

    with pytest.raises(LedgerCorruptError):
        guard(ledger_path).status("openai", KEY)


def test_ledger_with_unhashable_fields_fails_closed(ledger_path: Path) -> None:
    entry = {
        "ts": "t",
        "provider": ["openai"],
        "key_fp": KEY,
        "kind": "adjust",
        "usd": "1",
        "id": "x",
    }
    ledger_path.write_text(json.dumps(entry) + "\n")

    with pytest.raises(LedgerCorruptError):
        guard(ledger_path).status("openai", KEY)


def test_missing_ledger_is_refused_instead_of_resetting_the_cap(tmp_path: Path) -> None:
    uninitialised = BudgetGuard(Ledger(tmp_path / "nowhere" / "ledger.jsonl"), cap=Decimal("5.00"))

    with pytest.raises(LedgerMissingError, match="budget init"):
        uninitialised.reserve("openai", KEY, Decimal("0.01"), run_id="r1")


def test_initialise_creates_a_private_empty_ledger_once(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "var" / "ledger.jsonl")

    ledger.initialise()

    assert ledger.path.read_text() == ""
    assert ledger.path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        ledger.initialise()


def test_key_fingerprint_ignores_surrounding_whitespace() -> None:
    assert key_fingerprint(" sk-test-key\n") == key_fingerprint("sk-test-key")


def test_closing_a_reservation_that_was_never_made_is_rejected(ledger_path: Path) -> None:
    forged = Reservation(
        id="forged", provider="openai", key_fp=KEY, amount=Decimal("1"), run_id="r"
    )

    with pytest.raises(ValueError, match="no matching reservation"):
        guard(ledger_path).release(forged)


def test_closing_with_a_mismatched_key_is_rejected(ledger_path: Path) -> None:
    g = guard(ledger_path)
    real = g.reserve("openai", KEY, Decimal("0.10"), run_id="r1")
    tampered = Reservation(real.id, "openai", key_fingerprint("other"), real.amount, real.run_id)

    with pytest.raises(ValueError, match="no matching reservation"):
        g.commit(tampered, actual=None)


def test_concurrent_reservations_never_exceed_the_cap(ledger_path: Path) -> None:
    from concurrent.futures import ThreadPoolExecutor

    def attempt(i: int) -> bool:
        try:
            guard(ledger_path).reserve("openai", KEY, Decimal("0.50"), run_id=f"r{i}")
        except BudgetExceededError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=16) as pool:
        granted = sum(pool.map(attempt, range(40)))

    assert granted == 9  # floor(4.75 / 0.50): separate guards share only the locked file
    assert guard(ledger_path).status("openai", KEY).reserved == Decimal("4.50")


def test_ledger_that_is_not_utf8_fails_closed(ledger_path: Path) -> None:
    ledger_path.write_bytes(b"\xff\xfe\x00garbage")

    with pytest.raises(LedgerCorruptError, match="UTF-8"):
        guard(ledger_path).status("openai", KEY)
