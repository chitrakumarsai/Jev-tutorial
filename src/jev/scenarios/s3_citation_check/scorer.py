"""Score S3 findings against the approved key: per memo citation, the verdict. A wrong cited
section is noted on findings but not scored (presenter decision 2026-10-12)."""

from collections.abc import Mapping, Sequence
from functools import partial
from pathlib import Path

from jev.domain.findings import Finding
from jev.scenarios.s3_citation_check.answer_key import S3Key, S3KeyItem, load_s3_key
from jev.scoring.scorecard import ItemStatus, Scorecard, ScoreItem, Scorer, SummaryRow

FABRICATED = "fabricated"


def _citation_id(finding: Finding) -> str:
    """Pipelines name findings "<side>-<citation id>", e.g. "jev-C3"."""
    return finding.id.rsplit("-", 1)[-1].upper()


def _status(item: S3KeyItem, finding: Finding | None) -> ItemStatus:
    if finding is None or finding.verdict is None:
        return "missed"
    if finding.verdict != item.verdict:
        return "wrong_value"
    return "correct_in_review" if finding.lane == "review" else "correct"


def _summary(key: S3Key, statuses: Mapping[str, ItemStatus]) -> tuple[SummaryRow, ...]:
    def right(item: S3KeyItem) -> bool:
        return statuses[item.citation_id] in ("correct", "correct_in_review")

    fabricated = [i for i in key.items if i.verdict == FABRICATED]
    caught = bool(fabricated) and all(right(i) for i in fabricated)
    # Planted errors with a wrong verdict to catch; a planted wrong *section* (C1) is
    # verified by the key, so the only mistake there is over-flagging it.
    errors = [i for i in key.items if i.trap and i.verdict != "verified"]
    sections = [i for i in key.items if i.trap and i.verdict == "verified"]
    found = sum(right(i) for i in errors)
    kept = all(right(i) for i in sections)
    wrong = sum(s == "wrong_value" for s in statuses.values())
    rows = [
        SummaryRow(
            label="Fabricated quote caught", kind="text", value="Yes" if caught else "No", ok=caught
        ),
        SummaryRow(
            label="Planted errors caught",
            kind="text",
            value=f"{found} of {len(errors)}",
            ok=found == len(errors),
        ),
    ]
    if sections:
        rows.append(
            SummaryRow(
                label="Wrong-section citation kept",
                kind="text",
                value="Yes" if kept else "No",
                ok=kept,
            )
        )
    rows.append(SummaryRow(label="Wrong verdicts", kind="count", value=str(wrong), ok=wrong == 0))
    return tuple(rows)


def score(findings: Sequence[Finding], key: S3Key) -> Scorecard:
    """Findings for citations outside the key, or repeats, are false positives."""
    known = {item.citation_id for item in key.items}
    by_id: dict[str, Finding] = {}
    false_positives: list[str] = []
    for f in findings:  # one finding per known citation: the first with a verdict
        cid = _citation_id(f)
        held = by_id.get(cid)
        if cid not in known:
            false_positives.append(f.id)
        elif held is None or (held.verdict is None and f.verdict is not None):
            if held is not None:
                false_positives.append(held.id)
            by_id[cid] = f
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
    """A scorer bound to the approved S3 key."""
    return partial(score, key=load_s3_key(data_dir))
