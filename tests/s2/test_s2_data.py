"""S2 data: the addendum, the clause checklist and the hand-written answer key stay consistent."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from jev.scenarios.s2_clause_review.answer_key import S2KeyItem, load_s2_key
from jev.scenarios.s2_clause_review.checklist import load_checklist
from jev.scenarios.s2_clause_review.documents import SCENARIO_ID, load_s2_documents, scenario_dir
from jev.scenarios.s2_clause_review.validation import validate_s2_data

DATA = Path(__file__).resolve().parents[2] / "data"


def _copy(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    shutil.copytree(scenario_dir(DATA), scenario_dir(data))
    return data


def _edit_json(path: Path, change: Any) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    change(raw)
    path.write_text(json.dumps(raw), encoding="utf-8")


def test_bundled_data_is_consistent() -> None:
    assert validate_s2_data(DATA) == []


def test_the_addendum_is_one_document_short_enough_for_a_line_choice() -> None:
    docs = load_s2_documents(DATA)

    assert [d.doc_id for d in docs.documents] == ["addendum"]
    assert len(docs.documents[0].text.splitlines()) <= 255


def test_every_checklist_clause_has_a_four_level_rubric() -> None:
    checklist = load_checklist(DATA)

    assert checklist.scenario_id == SCENARIO_ID
    assert len(checklist.clauses) == 10
    assert all(len(c.risk_rubric) == 4 for c in checklist.clauses)


def test_the_key_plants_the_traps_from_the_plan() -> None:
    key = {item.clause_id: item for item in load_s2_key(DATA).items}

    assert key["breach_notification"].status == "absent"
    assert key["audit_rights"].status == "partial"
    assert key["insurance"].status == "partial"
    assert (key["limitation_of_liability"].status, key["limitation_of_liability"].risk) == (
        "present",
        "high",
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "absent", "risk": "high"},
        {"status": "absent", "quote": "x", "first_line": 1, "last_line": 1},
        {"status": "present", "quote": None},
        {"status": "present", "risk": None},
        {"status": "partial", "first_line": 9, "last_line": 3},
    ],
)
def test_a_key_item_must_be_internally_consistent(fields: dict[str, Any]) -> None:
    present = {
        "id": "K1",
        "clause_id": "governing_law",
        "status": "present",
        "first_line": 3,
        "last_line": 4,
        "quote": "Delaware",
        "risk": "low",
        "rationale": "r",
    }

    with pytest.raises(ValidationError):
        S2KeyItem.model_validate({**present, **fields})


def test_a_quote_outside_its_line_range_is_reported(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    key = scenario_dir(data) / "answer_key.json"

    def shift(raw: dict[str, Any]) -> None:
        item = next(i for i in raw["items"] if i["clause_id"] == "governing_law")
        item["first_line"] = item["last_line"] = 1

    _edit_json(key, shift)

    assert any("governing_law" in p and "not within lines" in p for p in validate_s2_data(data))


def test_a_clause_missing_from_the_key_is_reported(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    _edit_json(
        scenario_dir(data) / "answer_key.json",
        lambda raw: raw["items"].pop(),
    )

    assert any("not in the answer key" in p for p in validate_s2_data(data))


def test_an_absent_clause_whose_wording_appears_is_reported(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    addendum = scenario_dir(data) / "documents" / "addendum.md"
    addendum.write_text(
        addendum.read_text(encoding="utf-8") + "\n12.3 Carrier will notify Customer of any "
        "Security Incident within 72 hours.\n",
        encoding="utf-8",
    )

    assert any("breach_notification" in p and "absent" in p for p in validate_s2_data(data))


def test_an_unknown_clause_in_the_key_is_reported(tmp_path: Path) -> None:
    data = _copy(tmp_path)

    def rename(raw: dict[str, Any]) -> None:
        raw["items"][0]["clause_id"] = "no_such_clause"

    _edit_json(scenario_dir(data) / "answer_key.json", rename)

    assert any("no_such_clause" in p for p in validate_s2_data(data))
