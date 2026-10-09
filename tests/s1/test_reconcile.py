"""The reconciler is pure Decimal code: true facts must reproduce the answer key exactly."""

from dataclasses import replace
from datetime import date
from decimal import Decimal

from jev.scenarios.s1_reconciliation.reconcile import reconcile
from jev.scoring.answer_key import load_answer_key
from tests.s1.facts import DATA, TRUE_TERMS, true_facts

KEY = load_answer_key(DATA / "scenarios" / "s1_reconciliation" / "answer_key.json")


def as_tuples(findings):  # type: ignore[no-untyped-def]
    return sorted((f.kind, f.doc_id, f.line_ref, f.billed, f.expected) for f in findings)


def test_true_facts_reproduce_the_answer_key_exactly() -> None:
    findings = reconcile(TRUE_TERMS, true_facts())

    expected = sorted((i.kind, i.doc_id, i.line_ref, i.billed, i.expected) for i in KEY.items)
    assert as_tuples(findings) == expected
    assert sum((f.variance for f in findings), Decimal("0")) == KEY.total_variance


def test_input_order_does_not_matter() -> None:
    assert as_tuples(reconcile(TRUE_TERMS, list(reversed(true_facts())))) == as_tuples(
        reconcile(TRUE_TERMS, true_facts())
    )


def test_legitimate_late_fee_is_not_flagged() -> None:
    findings = reconcile(TRUE_TERMS, true_facts())

    assert not [f for f in findings if f.doc_id == "inv-2026-05"]


def test_late_fee_inside_grace_period_is_flagged() -> None:
    facts = true_facts()
    i5 = next(i for i, f in enumerate(facts) if f.invoice.number == "INV-2026-05")
    fee = facts[i5].late_fees[0]
    facts[i5] = replace(facts[i5], late_fees=(replace(fee, paid_on=date(2026, 4, 20)),))

    flagged = [f for f in reconcile(TRUE_TERMS, facts) if f.doc_id == "inv-2026-05"]

    assert [(f.kind, f.expected, f.variance) for f in flagged] == [
        ("late_fee_incorrect", Decimal("0.00"), Decimal("4075.08"))
    ]


def test_wrong_contract_terms_change_the_findings() -> None:
    no_cap_breach = replace(TRUE_TERMS, fuel_cap_pct=Decimal("25"))

    kinds = {f.kind for f in reconcile(no_cap_breach, true_facts())}

    assert "surcharge_over_cap" not in kinds


def test_rate_mismatch_is_detected() -> None:
    cheaper = replace(TRUE_TERMS, detention_rate=Decimal("80.00"))

    mismatches = [f for f in reconcile(cheaper, true_facts()) if f.kind == "rate_mismatch"]

    assert {f.doc_id for f in mismatches} == {
        "inv-2026-02",
        "inv-2026-05",
        "inv-2026-10",
        "inv-2026-12",
    }


def test_surcharge_without_a_stated_rate_is_skipped_not_guessed() -> None:
    facts = true_facts()
    first = facts[0]
    rows = tuple(
        replace(lf, row=replace(lf.row, stated_percent=None)) if lf.kind == "fuel_surcharge" else lf
        for lf in first.lines
    )
    facts[0] = replace(first, lines=rows)

    assert not [f for f in reconcile(TRUE_TERMS, facts) if f.doc_id == "inv-2026-01"]
