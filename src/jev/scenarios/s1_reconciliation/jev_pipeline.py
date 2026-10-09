"""S1 on the Jev side: code finds candidates, Jev judges what they mean (typed, calibrated),
code reconciles in Decimal, and anything uncertain goes to the auditor review lane."""

import asyncio
from dataclasses import dataclass

from jev.domain.documents import DocumentSet
from jev.domain.findings import Finding, SpanRef
from jev.domain.money import parse_money
from jev.extraction.invoice_table import ParsedInvoice, parse_invoice
from jev.providers.jev.port import JevPort
from jev.providers.jev.types import JevRequest, JevResult
from jev.scenarios.base import EventSink, SideOutput
from jev.scenarios.s1_reconciliation.jev_questions import (
    CONTRACT_PURPOSE,
    LINE_KIND_CRITERIA,
    NONE,
    TERM_SPECS,
    QuestionSet,
    contract_questions,
    invoice_questions,
)
from jev.scenarios.s1_reconciliation.reconcile import reconcile
from jev.scenarios.s1_reconciliation.terms import (
    ContractTerms,
    InvoiceFacts,
    LateFeeFact,
    LineFact,
    LineKind,
    ReconFinding,
)
from jev.scoring.metrics import CallUsage

MAX_CONCURRENCY = 4
NOUL_YES = 0.5
TERM_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "discount_not_applied": ("discount_threshold", "discount_pct"),
    "surcharge_on_undiscounted_base": ("discount_threshold", "discount_pct"),
    "surcharge_over_cap": ("fuel_cap_pct",),
    "duplicate_line": (),
    "late_fee_incorrect": ("late_fee_pct", "late_fee_grace_days"),
    "rate_mismatch": ("zone_a_rate", "zone_b_rate", "detention_rate"),
}


@dataclass(frozen=True)
class Judged:
    value: str
    confidence: float


Answers = dict[tuple[str, str], Judged]


def _index(requests: list[JevRequest], results: list[JevResult]) -> Answers:
    answers: Answers = {}
    for request, result in zip(requests, results, strict=True):
        for key, choice in result.choices.items():
            answers[(request.purpose, key)] = Judged(choice.choice, choice.confidence)
        for key, noul in result.nouls.items():
            answers[(request.purpose, key)] = Judged(f"{noul.noul:.4f}", noul.confidence)
    return answers


def _parse_term(kind: str, value: str) -> object:
    if kind == "money":
        return parse_money(value)
    if kind == "percent":
        return parse_money(value.rstrip("%"))
    return int(value.replace(",", ""))


class JevS1Pipeline:
    def __init__(self, documents: DocumentSet, *, review_threshold: float, run_id: str) -> None:
        self._docs = documents
        self._threshold = review_threshold
        self._invoices = [parse_invoice(d) for d in documents.documents if d.doc_id != "msa"]
        self._contract = contract_questions(documents.get("msa"), run_id)
        self._invoice_qs: list[QuestionSet] = [
            invoice_questions(documents.get(inv.doc_id), inv, run_id) for inv in self._invoices
        ]

    def requests(self) -> list[JevRequest]:
        return [self._contract.request, *(qs.request for qs in self._invoice_qs)]

    async def run(self, jev: JevPort, emit: EventSink) -> SideOutput:
        requests = self.requests()
        emit(
            "step",
            "jev",
            {
                "step": "candidates",
                "requests": len(requests),
                "questions": sum(len(r.questions) for r in requests),
            },
        )
        results = await self._ask_all(jev, requests, emit)
        answers = _index(requests, results)
        usages = tuple(
            CallUsage(input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens)
            for r in results
        )
        models = tuple(sorted({r.model for r in results}))
        terms, notes = self._terms(answers)
        if terms is None:
            emit("step", "jev", {"step": "gated", "review": 0, "notes": list(notes)})
            return SideOutput((), usages, models, notes)
        facts, fact_notes = self._facts(answers)
        recon = reconcile(terms, facts)
        emit("step", "jev", {"step": "computed", "findings": len(recon)})
        findings = tuple(self._finding(r, answers) for r in recon)
        for finding in findings:
            emit("finding", "jev", {"finding": finding.model_dump(mode="json")})
        emit("step", "jev", {"step": "gated", "review": sum(f.lane == "review" for f in findings)})
        return SideOutput(findings, usages, models, (*notes, *fact_notes))

    async def _ask_all(
        self, jev: JevPort, requests: list[JevRequest], emit: EventSink
    ) -> list[JevResult]:
        gate = asyncio.Semaphore(MAX_CONCURRENCY)

        async def ask(request: JevRequest) -> JevResult:
            async with gate:
                emit(
                    "step",
                    "jev",
                    {
                        "step": "request_sent",
                        "purpose": request.purpose,
                        "questions": len(request.questions),
                    },
                )
                result = await jev.evaluate(request)
                emit(
                    "step",
                    "jev",
                    {
                        "step": "answers",
                        "purpose": request.purpose,
                        "latency_ms": result.latency_ms,
                        "choices": {k: [a.choice, a.confidence] for k, a in result.choices.items()},
                        "nouls": {k: a.noul for k, a in result.nouls.items()},
                    },
                )
                return result

        return list(await asyncio.gather(*(ask(r) for r in requests)))

    def _terms(self, answers: Answers) -> tuple[ContractTerms | None, tuple[str, ...]]:
        values: dict[str, object] = {}
        missing = []
        for spec in TERM_SPECS:
            judged = answers.get((CONTRACT_PURPOSE, spec.name))
            if (
                judged is None
                or judged.value == NONE
                or judged.value not in self._contract.candidates[spec.name]
            ):
                missing.append(spec.name)
                continue
            values[spec.name] = _parse_term(spec.kind, judged.value)
        if missing:
            return None, tuple(
                f"Contract term not found: {name}; reconciliation needs review." for name in missing
            )
        return ContractTerms(**values), ()  # type: ignore[arg-type]

    def _facts(self, answers: Answers) -> tuple[list[InvoiceFacts], tuple[str, ...]]:
        facts, notes = [], []
        for invoice, qs in zip(self._invoices, self._invoice_qs, strict=True):
            built = self._invoice_facts(invoice, qs, answers)
            if built is None:
                notes.append(
                    f"Could not date {invoice.number}; excluded from reconciliation, needs review."
                )
            else:
                facts.append(built)
        return facts, tuple(notes)

    def _invoice_facts(
        self, invoice: ParsedInvoice, qs: QuestionSet, answers: Answers
    ) -> InvoiceFacts | None:
        purpose = qs.request.purpose
        dated = answers.get((purpose, "invoice_date"))
        if dated is None or dated.value not in qs.candidates["invoice_date"]:
            return None
        lines = tuple(
            LineFact(row, self._kind(answers, purpose, row.line_ref)) for row in invoice.rows
        )
        duplicates = {}
        for key in qs.request.questions:
            judged = answers.get((purpose, key))
            if key.startswith("dup_") and judged and float(judged.value) > NOUL_YES:
                _, first, second = key.split("_")
                duplicates[second] = first
        return InvoiceFacts(
            invoice=invoice,
            invoice_date=qs.candidates["invoice_date"][dated.value].as_date(),
            lines=lines,
            duplicate_of=duplicates,
            late_fees=self._late_fees(lines, qs, answers),
        )

    @staticmethod
    def _kind(answers: Answers, purpose: str, ref: str) -> LineKind:
        judged = answers.get((purpose, f"kind_{ref}"))
        value = judged.value if judged else "other"
        return value if value in LINE_KIND_CRITERIA else "other"  # type: ignore[return-value]

    @staticmethod
    def _late_fees(
        lines: tuple[LineFact, ...], qs: QuestionSet, answers: Answers
    ) -> tuple[LateFeeFact, ...]:
        fees = []
        for line in lines:
            ref, purpose = line.row.line_ref, qs.request.purpose
            picks = {k: answers.get((purpose, f"{k}_{ref}")) for k in ("paid", "refinv", "base")}
            if line.kind != "late_fee" or any(p is None or p.value == NONE for p in picks.values()):
                continue
            paid, refinv, base = (picks[k].value for k in ("paid", "refinv", "base"))  # type: ignore[union-attr]
            if paid not in qs.candidates.get(f"paid_{ref}", {}):
                continue
            fees.append(
                LateFeeFact(
                    ref, refinv, qs.candidates[f"paid_{ref}"][paid].as_date(), parse_money(base)
                )
            )
        return tuple(fees)

    def _finding(self, recon: ReconFinding, answers: Answers) -> Finding:
        purpose = f"s1.invoice.{recon.doc_id}"
        terms = TERM_DEPENDENCIES.get(recon.kind, ())
        needed = {f"contract.{t}": (CONTRACT_PURPOSE, t) for t in terms} | {
            f"{recon.doc_id}.{key}": (purpose, key)
            for key in [f"kind_{r}" for r in recon.line_refs] + ["invoice_date"]
        }
        used = {name: answers[at] for name, at in needed.items() if at in answers}
        missing = [name for name, at in needed.items() if at not in answers]
        for (p, key), judged in answers.items():
            if (
                p == purpose
                and key.startswith(("dup_", "paid_", "refinv_", "base_"))
                and key.endswith(recon.line_refs)
            ):
                used[f"{recon.doc_id}.{key}"] = judged
        low = [
            f"{name} ({j.confidence:.2f})"
            for name, j in used.items()
            if j.confidence < self._threshold
        ]
        flipped = [
            t
            for t in terms
            if (CONTRACT_PURPOSE, f"{t}__rev") in answers
            and (CONTRACT_PURPOSE, t) in answers
            and answers[(CONTRACT_PURPOSE, f"{t}__rev")].value
            != answers[(CONTRACT_PURPOSE, t)].value
        ]
        reasons = (
            ([f"missing answer: {', '.join(missing)}"] if missing else [])
            + ([f"low confidence: {', '.join(low)}"] if low else [])
            + ([f"option order changed the answer: {', '.join(flipped)}"] if flipped else [])
        )
        return Finding(
            id=f"jev:{recon.doc_id}:{recon.kind}:{recon.line_ref}",
            kind=recon.kind,
            doc_id=recon.doc_id,
            line_ref=recon.line_ref,
            billed=recon.billed,
            expected=recon.expected,
            variance=recon.variance,
            lane="review" if reasons else "auto",
            confidence=min((j.confidence for j in used.values()), default=None),
            review_reason="; ".join(reasons) or None,
            evidence=self._evidence(recon, answers, terms),
        )

    def _evidence(
        self, recon: ReconFinding, answers: Answers, terms: tuple[str, ...]
    ) -> tuple[SpanRef, ...]:
        invoice = next(i for i in self._invoices if i.doc_id == recon.doc_id)
        rows = [r.span for r in invoice.rows if r.line_ref in recon.line_refs]
        clauses = []
        for term in terms:
            judged = answers.get((CONTRACT_PURPOSE, term))
            cand = self._contract.candidates[term].get(judged.value) if judged else None
            if cand and cand.spans:
                clauses.append(cand.spans[0])
        return (*rows, *clauses)
