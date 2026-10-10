"""Scorecard: compare one side's findings with the answer key exactly, without cherry-picking."""

from decimal import Decimal
from pathlib import Path

import pytest

from jev.domain.findings import Finding
from jev.scenarios.s1_reconciliation.scorer import score
from jev.scoring.answer_key import AnswerKey, load_answer_key
from jev.scoring.metrics import CallUsage, metrics_for
from jev.scoring.scorecard import Scorecard, SummaryRow, VarianceTotal

KEY = load_answer_key(
    Path(__file__).resolve().parents[2]
    / "data"
    / "scenarios"
    / "s1_reconciliation"
    / "answer_key.json"
)


def _v(card: Scorecard) -> VarianceTotal:
    assert card.variance is not None  # S1 always reports a total variance
    return card.variance


def perfect_findings(key: AnswerKey) -> list[Finding]:
    return [
        Finding(id=f"F{i}", kind=item.kind, doc_id=item.doc_id, variance=item.variance)
        for i, item in enumerate(key.items)
    ]


def test_perfect_auto_findings_score_full_marks() -> None:
    card = score(perfect_findings(KEY), KEY)

    assert (card.correct, card.correct_in_review, card.of) == (14, 0, 14)
    assert card.false_positives == ()
    assert _v(card).reported == _v(card).expected == Decimal("98510.71")
    assert _v(card).exact is True


def _row(card: Scorecard, label: str) -> SummaryRow:
    return next(row for row in card.summary if row.label == label)


def test_s1_summary_rows_carry_wrong_amounts_and_the_total_variance() -> None:
    findings = perfect_findings(KEY)
    first_variance = findings[0].variance
    assert first_variance is not None
    findings[0] = findings[0].model_copy(update={"variance": first_variance + Decimal("1.00")})

    card = score(findings, KEY)

    assert [row.label for row in card.summary] == ["Wrong amounts", "Total variance"]
    assert _row(card, "Wrong amounts") == SummaryRow(
        label="Wrong amounts", kind="count", value="1", ok=False
    )
    total = _row(card, "Total variance")
    assert (total.kind, total.value, total.note, total.ok) == ("money", "98511.71", None, False)


def test_s1_summary_says_when_the_total_is_exact_or_not_reported() -> None:
    unreported = perfect_findings(KEY)[0].model_copy(update={"variance": None})

    exact = _row(score(perfect_findings(KEY), KEY), "Total variance")
    missing = _row(score([unreported], KEY), "Total variance")

    assert (exact.value, exact.note, exact.ok) == ("98510.71", "exact", True)
    assert (missing.value, missing.note, missing.ok) == (None, "Not reported", False)


def test_correct_finding_in_review_lane_is_reported_separately() -> None:
    findings = perfect_findings(KEY)
    findings[0] = findings[0].model_copy(update={"lane": "review"})

    card = score(findings, KEY)

    assert card.correct == 13
    assert card.correct_in_review == 1
    assert card.items[0].status == "correct_in_review"


def test_wrong_amount_and_missed_items() -> None:
    findings = perfect_findings(KEY)
    findings[0] = findings[0].model_copy(
        update={"variance": findings[0].variance + Decimal("0.01")}
    )
    del findings[1]

    card = score(findings, KEY)

    statuses = {item.key_id: item.status for item in card.items}
    assert statuses["K01"] == "wrong_value"
    assert statuses["K02"] == "missed"
    assert card.correct == 12
    assert _v(card).exact is False


def test_unmatched_and_duplicate_findings_are_false_positives() -> None:
    findings = [
        *perfect_findings(KEY),
        Finding(id="X1", kind="rate_mismatch", doc_id="inv-2026-01", variance=Decimal("10")),
        Finding(id="X2", kind=KEY.items[0].kind, doc_id=KEY.items[0].doc_id, variance=Decimal("1")),
    ]

    card = score(findings, KEY)

    assert card.correct == 14
    assert set(card.false_positives) == {"X1", "X2"}


def test_flagging_the_legitimate_late_fee_is_a_trap_hit() -> None:
    trap = Finding(
        id="T1",
        kind="late_fee_incorrect",
        doc_id="inv-2026-05",
        line_ref="L5",
        variance=Decimal("4075.08"),
    )

    card = score([*perfect_findings(KEY), trap], KEY)

    assert card.trap_hits == ("T1",)
    assert "T1" in card.false_positives


def test_missing_variance_counts_as_wrong_amount_and_hides_the_total() -> None:
    findings = perfect_findings(KEY)
    findings[0] = findings[0].model_copy(update={"variance": None})

    card = score(findings, KEY)

    assert card.items[0].status == "wrong_value"
    assert _v(card).reported is None
    assert _v(card).exact is False


def test_empty_answer_misses_everything() -> None:
    card = score([], KEY)

    assert card.correct == 0
    assert all(item.status == "missed" for item in card.items)
    assert _v(card).reported == Decimal("0")


def test_metrics_sum_tokens_and_price_them() -> None:
    usages = [
        CallUsage(input_tokens=1_000, output_tokens=400),
        CallUsage(input_tokens=2_000, output_tokens=0),
    ]

    metrics = metrics_for("gpt-6-luna", usages, wall_ms=2_300)

    assert (metrics.requests, metrics.input_tokens, metrics.output_tokens) == (2, 3_000, 400)
    assert metrics.cost_usd == Decimal("0.0005")  # 3,000 x 0.10/M + 400 x 0.50/M
    assert metrics.latency_ms == 2_300


def test_unknown_usage_makes_cost_unknown_rather_than_wrong() -> None:
    metrics = metrics_for(
        "jev-latest", [CallUsage(input_tokens=None, output_tokens=None)], wall_ms=150
    )

    assert metrics.cost_usd is None
    assert metrics.input_tokens == 0


def test_finding_rejects_negative_confidence() -> None:
    with pytest.raises(ValueError):
        Finding(id="F", kind="duplicate_line", doc_id="d", confidence=-0.1)


def _two_duplicates_key() -> AnswerKey:
    raw = KEY.model_dump(mode="json")
    dup = next(i for i in raw["items"] if i["kind"] == "duplicate_line")
    second = {
        **dup,
        "id": "K99",
        "line_ref": "L6",
        "billed": "85.00",
        "expected": "0.00",
        "variance": "85.00",
    }
    raw["items"].append(second)
    raw["total_variance"] = str(Decimal(raw["total_variance"]) + Decimal("85.00"))
    return AnswerKey.model_validate(raw)


def test_matching_prefers_the_same_line_regardless_of_finding_order() -> None:
    key = _two_duplicates_key()
    others = [f for f in perfect_findings(key) if f.kind != "duplicate_line"]
    on_l6 = Finding(
        id="D6",
        kind="duplicate_line",
        doc_id="inv-2026-10",
        line_ref="L6",
        variance=Decimal("85.00"),
    )
    on_l5 = Finding(
        id="D5",
        kind="duplicate_line",
        doc_id="inv-2026-10",
        line_ref="L5",
        variance=Decimal("510.00"),
    )

    card = score([*others, on_l6, on_l5], key)

    by_key = {i.key_id: (i.status, i.finding_id) for i in card.items}
    dup_ids = [i.id for i in key.items if i.kind == "duplicate_line"]
    assert by_key[dup_ids[0]] == ("correct", "D5")
    assert by_key["K99"] == ("correct", "D6")
    assert card.false_positives == ()


def test_matching_by_amount_when_the_line_is_not_reported() -> None:
    key = _two_duplicates_key()
    others = [f for f in perfect_findings(key) if f.kind != "duplicate_line"]
    small = Finding(id="A", kind="duplicate_line", doc_id="inv-2026-10", variance=Decimal("85.00"))
    big = Finding(id="B", kind="duplicate_line", doc_id="inv-2026-10", variance=Decimal("510.00"))

    card = score([*others, small, big], key)

    assert card.correct == 15


@pytest.mark.parametrize(
    ("kind", "value"), [("count", "1.5"), ("count", "-1"), ("money", "1,250.00"), ("money", "abc")]
)
def test_a_summary_value_must_suit_its_kind(kind: str, value: str) -> None:
    with pytest.raises(ValueError, match="summary value"):
        SummaryRow(label="x", kind=kind, value=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("kind", "value"), [("count", "12"), ("money", "-12.50"), ("text", "anything"), ("money", None)]
)
def test_a_summary_value_that_suits_its_kind_is_kept(kind: str, value: str | None) -> None:
    assert SummaryRow(label="x", kind=kind, value=value).value == value  # type: ignore[arg-type]
