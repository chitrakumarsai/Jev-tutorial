"""One Finding shape for every scenario: S1 money, S2 clause verdicts and risk, S3 citations."""

import pytest
from pydantic import ValidationError

from jev.domain.findings import Finding
from jev.scoring.scorecard import ScoreItem


def test_s1_findings_need_none_of_the_new_fields() -> None:
    finding = Finding(id="F1", kind="duplicate_line", doc_id="inv-2026-10")

    assert (finding.verdict, finding.risk, finding.claim) == (None, None, None)


def test_an_s2_clause_finding_carries_its_verdict_and_risk() -> None:
    finding = Finding(
        id="F1", kind="limitation_of_liability", doc_id="addendum", verdict="present", risk="high"
    )

    assert (finding.verdict, finding.risk) == ("present", "high")


def test_an_s3_citation_finding_carries_its_claim_and_verdict() -> None:
    finding = Finding(
        id="C3",
        kind="citation",
        doc_id="memo",
        verdict="fabricated",
        claim="The volume discount starts after 800 loads.",
    )

    assert finding.verdict == "fabricated"
    assert finding.claim is not None and "800 loads" in finding.claim


@pytest.mark.parametrize(("field", "value"), [("verdict", "maybe"), ("risk", "severe")])
def test_unknown_verdicts_and_risk_levels_are_refused(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate({"id": "F1", "kind": "x", "doc_id": "d", field: value})


def test_new_fields_round_trip_through_json() -> None:
    finding = Finding(id="F1", kind="audit_rights", doc_id="addendum", verdict="partial")

    assert Finding.model_validate_json(finding.model_dump_json()) == finding


def test_a_score_item_may_carry_a_display_label() -> None:
    item = ScoreItem(key_id="K3", status="missed", finding_id=None, label="Breach notification")

    assert item.label == "Breach notification"
    assert ScoreItem(key_id="K1", status="correct", finding_id="F1").label is None


@pytest.mark.parametrize(
    "fields",
    [
        {"verdict": "verified", "risk": "high"},
        {"verdict": "fabricated", "risk": "low"},
        {"verdict": "present", "claim": "A claim."},
        {"verdict": "absent", "risk": "high"},
    ],
)
def test_fields_that_do_not_fit_the_verdict_are_refused(fields: dict[str, str]) -> None:
    with pytest.raises(ValidationError, match="does not fit"):
        Finding.model_validate({"id": "F1", "kind": "x", "doc_id": "d", **fields})


def test_all_new_fields_round_trip_and_are_frozen() -> None:
    finding = Finding(id="F1", kind="c", doc_id="memo", verdict="contradicted", claim="X.")

    assert Finding.model_validate_json(finding.model_dump_json()) == finding
    with pytest.raises(ValidationError):
        finding.verdict = "verified"  # type: ignore[misc]
