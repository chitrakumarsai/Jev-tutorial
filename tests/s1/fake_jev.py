"""A stand-in for Jev that answers S1 questions like a perfect reader, with injectable faults."""

import re
from dataclasses import dataclass, field

from jev.domain.documents import Document
from jev.extraction.invoice_table import parse_invoice
from jev.providers.jev.types import ChoiceA, JevRequest, JevResult, NoulA, Usage
from tests.s1.facts import kind_of

TRUE_TERMS = {
    "zone_a_rate": "$1,250.00",
    "zone_b_rate": "$1,480.00",
    "detention_rate": "$85.00",
    "discount_threshold": "1,000",
    "discount_pct": "5%",
    "fuel_cap_pct": "18%",
    "late_fee_pct": "1.5%",
    "late_fee_grace_days": "30",
}
_INVOICE_DATE = re.compile(r"\*\*Invoice date:\*\* (\d{1,2} \w+ \d{4})")


@dataclass
class FakeJev:
    confidence: float = 0.97
    # (purpose, question key) -> forced choice value / confidence / noul
    choices: dict[tuple[str, str], str] = field(default_factory=dict)
    confidences: dict[tuple[str, str], float] = field(default_factory=dict)
    nouls: dict[tuple[str, str], float] = field(default_factory=dict)
    omitted: set[tuple[str, str]] = field(default_factory=set)  # answers Jev leaves out
    requests: list[JevRequest] = field(default_factory=list)

    async def evaluate(self, request: JevRequest) -> JevResult:
        self.requests.append(request)
        choices, nouls = {}, {}
        for key, question in request.questions.items():
            where = (request.purpose, key)
            if where in self.omitted:
                continue
            if question.type == "noul":
                nouls[key] = NoulA(noul=self.nouls.get(where, 0.98))
                continue
            value = self.choices.get(where) or self._truth(request, key)
            conf = self.confidences.get(where, self.confidence)
            options = list(question.criteria)
            probabilities = {
                o: (conf if o == value else (1 - conf) / max(len(options) - 1, 1)) for o in options
            }
            choices[key] = ChoiceA(choice=value, probabilities=probabilities, confidence=conf)
        return JevResult(
            model="jev-1.13.0",
            latency_ms=150,
            choices=choices,
            scores={},
            nouls=nouls,
            usage=Usage(input_tokens=1_000, output_tokens=40),
        )

    @staticmethod
    def _truth(request: JevRequest, key: str) -> str:
        base = key.removesuffix("__rev")
        if base in TRUE_TERMS:
            return TRUE_TERMS[base]
        text = request.state["invoice"]  # type: ignore[index]
        assert isinstance(text, str)
        if key == "invoice_date":
            match = _INVOICE_DATE.search(text)
            assert match
            return match.group(1)
        ref = key.split("_", 1)[1]
        if key.startswith("kind_"):
            row = next(
                r for r in parse_invoice(Document(doc_id="x", text=text)).rows if r.line_ref == ref
            )
            return kind_of(row.description)
        return {"paid": "11 May 2026", "refinv": "INV-2026-03", "base": "$271,672.00"}[
            key.split("_")[0]
        ]
