"""Score S3 findings against the approved key: per memo citation, the verdict. A wrong cited
section is noted on findings but not scored (presenter decision 2026-10-12)."""

from collections.abc import Sequence
from functools import partial
from pathlib import Path

from jev.domain.findings import Finding
from jev.scenarios.s3_citation_check.answer_key import S3Key, S3KeyItem, load_s3_key
from jev.scoring.scorecard import ItemStatus, Scorecard, ScoreItem, Scorer, SummaryRow

FABRICATED = "fabricated"


def _citation_id(finding: Finding) -> str:
    """Pipelines name findings "<side>-<citation id>", e.g. "jev-C3"."""
    return finding.id.rsplit("-", 1)[-1]


def _status(item: S3KeyItem, finding: Finding | None) -> ItemStatus:
    if finding is None or finding.verdict is None:
        return "missed"
    if finding.verdict != item.verdict:
        return "wrong_value"
    return "correct_in_review" if finding.lane == "review" else "correct"


def _summary(key: S3Key, statuses: dict[str, ItemStatus]) -> tuple[SummaryRow, ...]:
    fabricated = [i for i in key.items if i.verdict == FABRICATED]
    caught = all(statuses[i.citation_id] in ("correct", "correct_in_review") for i in fabricated)
    traps = [i for i in key.items if i.trap]
    found = sum(statuses[i.citation_id] in ("correct", "correct_in_review") for i in traps)
    wrong = sum(s == "wrong_value" for s in statuses.values())
    return (
        SummaryRow(
            label="Fabricated quote caught", kind="text", value="Yes" if caught else "No", ok=caught
        ),
        SummaryRow(
            label="Planted errors caught",
            kind="text",
            value=f"{found} of {len(traps)}",
            ok=found == len(traps),
        ),
        SummaryRow(label="Wrong verdicts", kind="count", value=str(wrong), ok=wrong == 0),
    )


def score(findings: Sequence[Finding], key: S3Key) -> Scorecard:
    """Findings for citations outside the key, or repeats, are false positives."""
    known = {item.citation_id for item in key.items}
    by_id: dict[str, Finding] = {}
    false_positives: list[str] = []
    for f in findings:  # the first finding per known citation is scored; the rest are not
        if _citation_id(f) in known and _citation_id(f) not in by_id:
            by_id[_citation_id(f)] = f
        else:
            false_positives.append(f.id)
    statuses = {i.citation_id: _status(i, by_id.get(i.citation_id)) for i in key.items}
    items = tuple(
        ScoreItem(
            key_id=i.id,
            status=statuses[i.citation_id],
            finding_id=by_id[i.citation_id].id if i.citation_id in by_id else None,
            label=i.citation_id,
        )
        for i in key.items
    )
    # A trap is hit only by a confident (auto-lane) wrong verdict on a planted error.
    trap_hits = tuple(
        f.id
        for i in key.items
        if i.trap
        and statuses[i.citation_id] == "wrong_value"
        and (f := by_id[i.citation_id]).lane == "auto"
    )
    return Scorecard(
        items=items,
        false_positives=tuple(false_positives),
        trap_hits=trap_hits,
        summary=_summary(key, statuses),
    )


def load_s3_scorer(data_dir: Path) -> Scorer:
    return partial(score, key=load_s3_key(data_dir))
