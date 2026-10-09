"""S1 documents load in order, stay small enough for Jev, and back every answer-key value."""

import shutil
from pathlib import Path

import pytest

from jev.cli import main
from jev.scenarios.s1_reconciliation.documents import (
    DocumentTooLargeError,
    load_s1_documents,
    validate_s1_data,
)

DATA = Path(__file__).resolve().parents[2] / "data"


def test_loads_contract_and_twelve_invoices_in_order() -> None:
    docs = load_s1_documents(DATA)

    assert [d.doc_id for d in docs.documents][:3] == ["msa", "inv-2026-01", "inv-2026-02"]
    assert len(docs.documents) == 13
    assert docs.get("inv-2026-10").text.startswith("# Invoice INV-2026-10")
    assert "Synthetic" in docs.get("msa").text


def test_unknown_document_id_raises() -> None:
    with pytest.raises(KeyError):
        load_s1_documents(DATA).get("inv-2027-01")


def test_bundled_data_is_valid() -> None:
    assert validate_s1_data(DATA) == []


def _copy_data(tmp_path: Path) -> Path:
    target = tmp_path / "data"
    shutil.copytree(DATA, target)
    return target


def test_oversized_document_is_rejected(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    invoice = data / "scenarios" / "s1_reconciliation" / "documents" / "invoices" / "inv-2026-01.md"
    invoice.write_text(invoice.read_text() + "padding " * 2_000)

    with pytest.raises(DocumentTooLargeError, match="inv-2026-01"):
        load_s1_documents(data)


def test_validation_reports_answer_key_values_missing_from_documents(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    invoice = data / "scenarios" / "s1_reconciliation" / "documents" / "invoices" / "inv-2026-04.md"
    invoice.write_text(invoice.read_text().replace("$57,530.00", "$57,531.00"))
    msa = data / "scenarios" / "s1_reconciliation" / "documents" / "msa.md"
    msa.write_text(msa.read_text().replace("may not exceed 18%", "may not exceed eighteen percent"))

    problems = validate_s1_data(data)

    assert any("K" in p and "inv-2026-04" in p and "$57,530.00" in p for p in problems)
    assert any("may not exceed 18%" in p for p in problems)


def test_cli_validate_succeeds_on_bundled_data(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["data", "validate", "--data-dir", str(DATA)]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_validate_fails_on_broken_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _copy_data(tmp_path)
    (data / "scenarios" / "s1_reconciliation" / "answer_key.json").write_text("{}")

    assert main(["data", "validate", "--data-dir", str(data)]) == 1
    assert "answer key" in capsys.readouterr().err.lower()


def test_cli_requires_a_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])


def test_cli_reports_consistency_problems(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _copy_data(tmp_path)
    key_path = data / "scenarios" / "s1_reconciliation" / "answer_key.json"
    key_path.write_text(key_path.read_text().replace('"inv-2026-10"', '"inv-2099-10"'))

    assert main(["data", "validate", "--data-dir", str(data)]) == 1
    assert "unknown document inv-2099-10" in capsys.readouterr().err


def test_cli_reports_missing_or_oversized_documents(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = _copy_data(tmp_path)
    (data / "scenarios" / "s1_reconciliation" / "documents" / "msa.md").unlink()

    assert main(["data", "validate", "--data-dir", str(data)]) == 1
    assert "Documents are invalid" in capsys.readouterr().err


def test_cli_budget_init_creates_the_ledger_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ledger = tmp_path / "var" / "ledger.jsonl"

    assert main(["budget", "init", "--ledger-path", str(ledger)]) == 0
    assert ledger.is_file()
    assert main(["budget", "init", "--ledger-path", str(ledger)]) == 1
    assert "already exists" in capsys.readouterr().err


def test_amounts_must_match_on_boundaries_not_as_substrings(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    invoice = data / "scenarios" / "s1_reconciliation" / "documents" / "invoices" / "inv-2026-10.md"
    # "$510.00" would still be a substring of "$1,510.00" if the check were naive.
    invoice.write_text(invoice.read_text().replace("| $510.00 |", "| $1,510.00 |"))

    problems = validate_s1_data(data)

    assert any("$510.00" in p and "inv-2026-10" in p for p in problems)


def test_unknown_evidence_document_is_reported_not_crashed(tmp_path: Path) -> None:
    data = _copy_data(tmp_path)
    key_path = data / "scenarios" / "s1_reconciliation" / "answer_key.json"
    key_path.write_text(key_path.read_text().replace('"doc_id": "msa"', '"doc_id": "contract"', 1))

    assert any("unknown evidence document contract" in p for p in validate_s1_data(data))
