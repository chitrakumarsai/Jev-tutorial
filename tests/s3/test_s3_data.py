"""S3 data: the planted memo and the hand-written key agree with the S1 documents."""

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from jev.scenarios.s3_citation_check.answer_key import S3KeyItem, load_s3_key
from jev.scenarios.s3_citation_check.documents import load_memo, scenario_dir
from jev.scenarios.s3_citation_check.validation import validate_s3_data
from tests.s1.facts import DATA


def _copy(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    shutil.copytree(DATA / "scenarios", data / "scenarios")
    return data


def _edit(path: Path, change: Any) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    change(raw)
    path.write_text(json.dumps(raw), encoding="utf-8")


def test_bundled_memo_and_key_are_consistent() -> None:
    assert validate_s3_data(DATA) == []


def test_the_key_plants_the_four_errors_from_the_plan() -> None:
    key = {item.citation_id: item for item in load_s3_key(DATA).items}

    assert key["C3"].verdict == "fabricated"
    assert key["C7"].verdict == "contradicted"
    assert key["C8"].verdict == "unsupported"
    assert (key["C1"].verdict, key["C1"].section_correct) == ("verified", False)
    others = [c for c in key if c not in {"C1", "C3", "C7", "C8"}]
    assert len(others) == 6
    assert all(key[c].verdict == "verified" and key[c].section_correct for c in others)
    assert {c for c, item in key.items() if item.trap} == {"C1", "C3", "C7", "C8"}


def test_the_memo_keeps_its_ten_citations_and_their_markers() -> None:
    memo = load_memo(DATA)

    assert [c.id for c in memo.citations] == [f"C{i}" for i in range(1, 11)]
    assert all(f"[{c.id}]" in memo.body for c in memo.citations)


def test_a_fabricated_quote_that_does_exist_is_reported(tmp_path: Path) -> None:
    data = _copy(tmp_path)

    def real_quote(raw: dict[str, Any]) -> None:
        c3 = next(c for c in raw["citations"] if c["id"] == "C3")
        c3["quote"] = "Customer receives a discount of 5% off all line-haul charges."

    _edit(scenario_dir(data) / "memo.json", real_quote)

    assert any("C3" in p and "fabricated" in p for p in validate_s3_data(data))


def test_a_wrong_section_flag_is_reported(tmp_path: Path) -> None:
    data = _copy(tmp_path)

    def claim_correct(raw: dict[str, Any]) -> None:
        next(i for i in raw["items"] if i["citation_id"] == "C1")["section_correct"] = True

    _edit(scenario_dir(data) / "answer_key.json", claim_correct)

    assert any("C1" in p and "section" in p for p in validate_s3_data(data))


def test_a_citation_missing_from_the_key_is_reported(tmp_path: Path) -> None:
    data = _copy(tmp_path)
    _edit(scenario_dir(data) / "answer_key.json", lambda raw: raw["items"].pop())

    assert any("not in the answer key" in p for p in validate_s3_data(data))


def test_a_fabricated_citation_has_no_section_to_judge() -> None:
    with pytest.raises(ValidationError):
        S3KeyItem(
            id="K3",
            citation_id="C3",
            verdict="fabricated",
            section_correct=True,
            rationale="r",
        )
