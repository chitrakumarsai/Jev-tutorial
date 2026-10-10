"""S2 on the Jev side: one Jev request judges, for every checklist clause, which line addresses
it, whether any line does, and how risky its terms are. Code turns those typed answers into a
verdict per clause and sends anything uncertain or only partly there to the review lane."""

from dataclasses import dataclass

from jev.domain.documents import DocumentSet
from jev.domain.findings import ClauseVerdict, Finding, Risk, SpanRef
from jev.providers.jev.port import JevPort
from jev.providers.jev.types import JevRequest, JevResult
from jev.scenarios.base import EventSink, SideOutput
from jev.scenarios.s2_clause_review.checklist import Checklist, ChecklistClause
from jev.scenarios.s2_clause_review.documents import ADDENDUM_ID
from jev.scenarios.s2_clause_review.jev_questions import (
    NumberedLine,
    clause_request,
    numbered_lines,
)
from jev.scoring.metrics import CallUsage

# From the semantic-find recipe, frozen before the key review (PLAN-M2 §3). Known limitation:
# "partial" comes from a binary Noul landing mid-range, which reads as uncertainty, not as
# "present but deficient"; a three-way question could separate the two in a later milestone.
PRESENT, ABSENT = 0.7, 0.35
RISKS: tuple[Risk, ...] = ("low", "medium", "high", "critical")
# Levels this close to the most likely one count as tied; a tie goes to the higher risk.
RISK_TIE = 0.05


@dataclass(frozen=True)
class Judgement:
    verdict: ClauseVerdict | None
    line: NumberedLine | None
    risk: Risk | None
    confidence: float | None
    reasons: tuple[str, ...]


def _verdict(noul: float) -> ClauseVerdict:
    return "present" if noul >= PRESENT else "absent" if noul < ABSENT else "partial"


def _risk(probabilities: dict[str, float]) -> Risk | None:
    """The most likely level, cautiously: near ties go to the higher risk. None when the
    answer has no readable level (keys are 0-based level indices as strings)."""
    levels = {int(k): p for k, p in probabilities.items() if k.isdigit() and int(k) < len(RISKS)}
    if not levels:
        return None
    top = max(levels.values())
    return RISKS[max(level for level, p in levels.items() if p >= top - RISK_TIE)]


def _judge(
    clause: ChecklistClause, result: JevResult, lines: dict[str, NumberedLine], threshold: float
) -> Judgement:
    exists = result.nouls.get(f"{clause.id}__exists")
    where = result.choices.get(f"{clause.id}__where")
    score = result.scores.get(f"{clause.id}__risk")
    if exists is None:
        reason = "Jev gave no answer on whether it is there"
        return Judgement(verdict=None, line=None, risk=None, confidence=None, reasons=(reason,))
    verdict = _verdict(exists.noul)
    reasons: list[str] = []
    # A partial verdict *is* a mid-range "exists" answer, so its near-zero confidence says
    # nothing more; the gate then rests on the other answers.
    confidences = [] if verdict == "partial" else [("exists", exists.confidence)]
    line = None
    if verdict != "absent":  # a line pick always names some line, so ignore it when absent
        if where is None:
            reasons.append("Jev gave no answer on where it is")
        else:
            line = lines.get(where.choice)
            confidences.append(("where", where.confidence))
            if line is None:
                reasons.append(f"Jev named line {where.choice}, which is not in the document")
    risk = _risk(score.probabilities) if score else None
    if score is None:
        reasons.append("Jev gave no answer on its risk")
    elif risk is None:
        reasons.append("Jev's risk answer was unreadable")
    else:
        confidences.append(("risk", score.confidence))
    if verdict == "partial":
        reasons.insert(0, "partial: related wording that may not do what the checklist asks")
    weakest = min(confidences, key=lambda named: named[1], default=None)
    if weakest and weakest[1] < threshold:
        reasons.append(f"{weakest[0]} {weakest[1]:.0%} is below {threshold:.0%}")
    return Judgement(
        verdict=verdict,
        line=line,
        risk=risk,
        confidence=weakest[1] if weakest else None,
        reasons=tuple(reasons),
    )


def _finding(clause: ChecklistClause, judged: Judgement) -> Finding:
    line = judged.line
    evidence = (
        (SpanRef(doc_id=ADDENDUM_ID, start=line.start, end=line.end, text=line.text),)
        if line
        else ()
    )
    return Finding(
        id=f"jev-{clause.id}",
        kind=clause.id,
        doc_id=ADDENDUM_ID,
        line_ref=line.id if line else None,
        verdict=judged.verdict,
        risk=judged.risk,
        confidence=judged.confidence,
        lane="review" if judged.reasons else "auto",
        review_reason="; ".join(judged.reasons) or None,
        evidence=evidence,
    )


class JevS2Pipeline:
    def __init__(
        self, documents: DocumentSet, checklist: Checklist, *, review_threshold: float, run_id: str
    ) -> None:
        addendum = documents.get(ADDENDUM_ID)
        self._checklist = checklist
        self._threshold = review_threshold
        self._lines = {line.id: line for line in numbered_lines(addendum)}
        self._request = clause_request(addendum, checklist, run_id=run_id)

    def requests(self) -> list[JevRequest]:
        return [self._request]

    async def run(self, jev: JevPort, emit: EventSink) -> SideOutput:
        request = self._request
        questions = len(request.questions)
        emit("step", "jev", {"step": "candidates", "requests": 1, "questions": questions})
        emit(
            "step",
            "jev",
            {"step": "request_sent", "purpose": request.purpose, "questions": questions},
        )
        result = await jev.evaluate(request)
        emit("step", "jev", _answers_event(request, result))
        findings = tuple(
            _finding(clause, _judge(clause, result, self._lines, self._threshold))
            for clause in self._checklist.clauses
        )
        emit("step", "jev", {"step": "computed", "findings": len(findings)})
        for finding in findings:
            emit("finding", "jev", {"finding": finding.model_dump(mode="json")})
        emit("step", "jev", {"step": "gated", "review": sum(f.lane == "review" for f in findings)})
        usage = CallUsage(
            input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens
        )
        return SideOutput(findings, (usage,), (result.model,))


def _answers_event(request: JevRequest, result: JevResult) -> dict[str, object]:
    return {
        "step": "answers",
        "purpose": request.purpose,
        "latency_ms": result.latency_ms,
        "choices": {k: [a.choice, a.confidence] for k, a in result.choices.items()},
        "nouls": {k: a.noul for k, a in result.nouls.items()},
        "scores": {
            k: [risk, a.confidence]
            for k, a in result.scores.items()
            if (risk := _risk(a.probabilities)) is not None
        },
    }
