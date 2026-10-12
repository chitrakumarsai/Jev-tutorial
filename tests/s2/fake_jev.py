"""A stand-in for Jev that answers S2 questions as the approved key says, with injectable faults."""

from dataclasses import dataclass, field

from jev.providers.jev.types import ChoiceA, JevRequest, JevResult, NoulA, ScoreA, Usage
from jev.scenarios.s2_clause_review.answer_key import S2Key

RISK_INDEX = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass
class FakeS2Jev:
    key: S2Key
    confidence: float = 0.95
    where_confidence: dict[str, float] = field(default_factory=dict)  # question key -> conf
    where_probabilities: dict[str, dict[str, float]] = field(default_factory=dict)
    statuses: dict[str, str] = field(default_factory=dict)  # question key -> forced status
    status_confidence: dict[str, float] = field(default_factory=dict)
    lines: dict[str, str] = field(default_factory=dict)  # question key -> forced line id
    risk_probabilities: dict[str, dict[str, float]] = field(default_factory=dict)
    omitted: set[str] = field(default_factory=set)
    requests: list[JevRequest] = field(default_factory=list)

    async def evaluate(self, request: JevRequest) -> JevResult:
        self.requests.append(request)
        truth = {item.clause_id: item for item in self.key.items}
        choices: dict[str, ChoiceA] = {}
        scores: dict[str, ScoreA] = {}
        nouls: dict[str, NoulA] = {}
        for qkey in request.questions:
            if qkey in self.omitted:
                continue
            clause_id, kind = qkey.split("__")
            item = truth[clause_id]
            if kind == "status":
                choice = self.statuses.get(qkey, item.status)
                conf = self.status_confidence.get(qkey, self.confidence)
                choices[qkey] = ChoiceA(
                    choice=choice, probabilities={choice: conf}, confidence=conf
                )
            elif kind == "where":
                line = self.lines.get(qkey) or f"L{item.first_line or 1:03d}"
                conf = self.where_confidence.get(qkey, self.confidence)
                probabilities = self.where_probabilities.get(qkey) or {line: conf}
                choices[qkey] = ChoiceA(choice=line, probabilities=probabilities, confidence=conf)
            else:
                probabilities = (
                    self.risk_probabilities[qkey]
                    if qkey in self.risk_probabilities
                    else {
                        str(RISK_INDEX[item.risk or "low"]): self.confidence,
                        "0" if item.risk != "low" else "1": 1 - self.confidence,
                    }
                )
                top = max(probabilities.values(), default=0.0)
                mean = sum(int(k) * p for k, p in probabilities.items() if k.isdigit())
                scores[qkey] = ScoreA(score=mean, probabilities=probabilities, confidence=top)
        return JevResult(
            model="jev-1.13.0",
            latency_ms=120,
            choices=choices,
            scores=scores,
            nouls=nouls,
            usage=Usage(input_tokens=2_400, output_tokens=60),
        )
