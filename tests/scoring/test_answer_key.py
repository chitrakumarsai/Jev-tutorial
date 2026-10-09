"""The S1 answer key is internally consistent and grounded in the documents."""

from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from jev.domain.money import format_money
from jev.scoring.answer_key import AnswerKey, load_answer_key

S1 = Path(__file__).resolve().parents[2] / "data" / "scenarios" / "s1_reconciliation"


@pytest.fixture(scope="module")
def key() -> AnswerKey:
    return load_answer_key(S1 / "answer_key.json")


def test_key_has_the_planted_findings(key: AnswerKey) -> None:
    kinds = [item.kind for item in key.items]

    assert len(key.items) == 14
    assert kinds.count("discount_not_applied") == 6
    assert kinds.count("surcharge_on_undiscounted_base") == 6
    assert kinds.count("surcharge_over_cap") == 1
    assert kinds.count("duplicate_line") == 1


def test_every_variance_and_the_total_recompute_exactly(key: AnswerKey) -> None:
    for item in key.items:
        assert item.billed - item.expected == item.variance, item.id

    assert sum((item.variance for item in key.items), Decimal("0")) == key.total_variance
    assert key.total_variance == Decimal("98510.71")


def test_discount_threshold_is_first_crossed_in_june(key: AnswerKey) -> None:
    months_over = [m for m, n in key.cumulative_loads_by_month.items() if n > 1000]

    assert months_over[0] == "2026-06"
    discounted_docs = {i.doc_id for i in key.items if i.kind == "discount_not_applied"}
    assert discounted_docs == {f"inv-2026-{m:02d}" for m in range(7, 13)}


def test_evidence_quotes_appear_verbatim_in_the_contract(key: AnswerKey) -> None:
    msa = (S1 / "documents" / "msa.md").read_text(encoding="utf-8")

    for item in key.items:
        assert item.evidence, item.id
        for evidence in item.evidence:
            assert evidence.quote in msa, (item.id, evidence.quote)


def test_billed_amounts_appear_on_the_invoices(key: AnswerKey) -> None:
    for item in key.items:
        text = (S1 / "documents" / "invoices" / f"{item.doc_id}.md").read_text(encoding="utf-8")
        assert format_money(item.billed) in text, (item.id, item.billed)


def test_late_fee_trap_is_recorded_as_a_non_issue(key: AnswerKey) -> None:
    assert [(n.doc_id, n.line_ref) for n in key.non_issues] == [("inv-2026-05", "L5")]
    assert "inv-2026-05" in key.clean_invoices


def _raw_item(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": "K01",
        "kind": "duplicate_line",
        "doc_id": "inv-2026-10",
        "line_ref": "L5",
        "billed": "510.00",
        "expected": "0.00",
        "variance": "510.00",
        "evidence": [{"doc_id": "msa", "quote": "q"}],
    }
    return {**item, **overrides}


def _raw_key(items: list[dict[str, object]], total: str) -> dict[str, object]:
    return {
        "scenario_id": "s1_reconciliation",
        "version": 1,
        "authored_at": "2026-10-09",
        "contract_terms": {},
        "cumulative_loads_by_month": {},
        "items": items,
        "clean_invoices": [],
        "non_issues": [],
        "total_variance": total,
    }


@pytest.mark.parametrize(
    ("items", "total"),
    [
        ([_raw_item(variance="500.00")], "500.00"),
        ([_raw_item()], "999.99"),
        ([_raw_item(), _raw_item()], "1020.00"),
        ([_raw_item(kind="vibes")], "510.00"),
    ],
)
def test_inconsistent_keys_are_rejected(items: list[dict[str, object]], total: str) -> None:
    with pytest.raises(ValidationError):
        AnswerKey.model_validate(_raw_key(items, total))


def test_missing_key_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_answer_key(tmp_path / "nope.json")
