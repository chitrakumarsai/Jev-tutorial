"""A stand-in for Jev that judges S3 citations as the approved key says, with injectable faults."""

from dataclasses import dataclass, field

from jev.providers.jev.types import ChoiceA, JevRequest, JevResult, Usage
from jev.scenarios.s3_citation_check.answer_key import S3Key

RELATION_OF = {"verified": "supports", "contradicted": "contradicts", "unsupported": "says_nothing"}


@dataclass
class FakeS3Jev:
    key: S3Key
    confidence: float = 0.95
    relations: dict[str, str] = field(default_factory=dict)  # citation id -> forced relation
    confidences: dict[str, float] = field(default_factory=dict)
    omitted: set[str] = field(default_factory=set)  # citation ids Jev leaves unanswered
    requests: list[JevRequest] = field(default_factory=list)

    async def evaluate(self, request: JevRequest) -> JevResult:
        self.requests.append(request)
        citation_id = request.purpose.rsplit(".", 1)[-1]
        verdict = next(i.verdict for i in self.key.items if i.citation_id == citation_id)
        choices = {}
        if citation_id not in self.omitted:
            relation = self.relations.get(citation_id, RELATION_OF.get(verdict, "supports"))
            conf = self.confidences.get(citation_id, self.confidence)
            choices["relation"] = ChoiceA(
                choice=relation, probabilities={relation: conf}, confidence=conf
            )
        return JevResult(
            model="jev-1.13.0",
            latency_ms=90,
            choices=choices,
            scores={},
            nouls={},
            usage=Usage(input_tokens=300, output_tokens=10),
        )
