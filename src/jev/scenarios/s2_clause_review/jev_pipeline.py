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

# From the semantic-find recipe, frozen before the key review (PLAN-M2 §3).
FOUND, ABSENT = 0.7, 0.35
RISKS: tuple[Risk, ...] = ("low", "medium", "high", "critical")


@dataclass(frozen=True)
class Judgement:
    verdict: ClauseVerdict | None
    line: NumberedLine | None
    risk: Risk | None
    confidence: float | None
    reasons: tuple[str, ...]


def _verdict(noul: float) -> ClauseVerdict:
    return "present" if noul >= FOUND else "absent" if noul < ABSENT else "partial"


def _risk(probabilities: dict[str, float]) -> Risk:
    """The most likely level; a tie goes to the higher risk (the cautious reading)."""
    level = max(probabilities, key=lambda k: (probabilities[k], int(k)))
    return RISKS[int(level)]


def _judge(
    clause: ChecklistClause, result: JevResult, lines: dict[str, NumberedLine], threshold: float
) -> Judgement:
    exists = result.nouls.get(f"{clause.id}__exists")
    where = result.choices.get(f"{clause.id}__where")
    risk = result.scores.get(f"{clause.id}__risk")
    if exists is None:
        return Judgement(None, None, None, None, ("Jev gave no answer on whether it is there",))
    verdict = _verdict(exists.noul)
    reasons: list[str] = []
    confidences = [exists.confidence]
    line = None
    if verdict != "absent":  # the line pick always names some line, so ignore it when absent
        if where is None:
            reasons.append("Jev gave no answer on where it is")
        else:
            line, confidences = lines.get(where.choice), [*confidences, where.confidence]
    if risk is None:
        reasons.append("Jev gave no answer on its risk")
    else:
        confidences.append(risk.confidence)
    confidence = min(confidences)
    if verdict == "partial":
        # Its "is it there" answer sits near a coin flip by definition; say why, not "0%".
        reasons.append("partial: related wording that may not do what the checklist asks")
    elif confidence < threshold:
        reasons.append(f"confidence {confidence:.0%} is below {threshold:.0%}")
    return Judgement(
        verdict, line, _risk(risk.probabilities) if risk else None, confidence, tuple(reasons)
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
        "scores": {k: [_risk(a.probabilities), a.confidence] for k, a in result.scores.items()},
    }
