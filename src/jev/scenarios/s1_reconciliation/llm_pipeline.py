"""S1 on the LLM side: one well-written structured-output prompt over the same documents.
The prompt is shown in the UI so the audience can judge its fairness."""

import re
from decimal import Decimal

from jev.domain.documents import DocumentSet
from jev.domain.findings import Finding
from jev.domain.money import parse_money
from jev.extraction.text import find_quote
from jev.providers.openai.port import LlmPort
from jev.providers.openai.types import LlmRequest
from jev.scenarios.base import EventSink, SideOutput
from jev.scenarios.s1_reconciliation.llm_schema import LlmFinding, S1LlmReport
from jev.scoring.metrics import CallUsage

LLM_PURPOSE = "s1.llm"
MAX_OUTPUT_TOKENS = 4_000

INSTRUCTIONS = """You are a meticulous freight-billing auditor.
You receive a Master Services Agreement (document id "msa") and twelve monthly invoices
(document ids "inv-2026-01" to "inv-2026-12"). Check every invoice against the agreement and
report every billing discrepancy. Do not report charges that the agreement allows.

Report each discrepancy once, using exactly one of these kinds:
- discount_not_applied: the volume discount should apply to line-haul charges but was not applied
  (line_ref: the line-haul lines joined with "+", e.g. "L1+L2"; amounts: line-haul subtotal)
- surcharge_on_undiscounted_base: the fuel surcharge was calculated on line-haul charges before
  a discount that should have applied
- surcharge_over_cap: the fuel surcharge percentage exceeds the contractual cap
- duplicate_line: the same charge is billed twice (report the second line; expected is 0.00)
- late_fee_incorrect: a late fee is not allowed, or is calculated incorrectly
- rate_mismatch: a quantity times the contractual rate does not equal the amount billed
- other: anything else that breaches the agreement

Rules:
- invoice_id is the invoice number, e.g. "INV-2026-07"; line_ref is the line, e.g. "L3".
- billed, expected and variance are decimal strings with two decimals, no currency symbols or
  thousands separators, e.g. "12392.50". variance = billed - expected.
- quote must be copied verbatim from the agreement: the clause that the discrepancy breaches.
- total_variance is the sum of all variances.
- If an invoice has no discrepancy, report nothing for it."""


def _amount(raw: str) -> Decimal | None:
    """Accept "12392.50" or "$12,392.50"; anything vaguer is unknown, never guessed."""
    try:
        return parse_money(raw)
    except ValueError:
        return None


class LlmS1Pipeline:
    def __init__(self, documents: DocumentSet, *, run_id: str) -> None:
        self._docs = documents
        self._run_id = run_id

    def request(self) -> LlmRequest:
        body = "\n\n".join(f"=== DOCUMENT {d.doc_id} ===\n{d.text}" for d in self._docs.documents)
        return LlmRequest(
            instructions=INSTRUCTIONS,
            input=body,
            purpose=LLM_PURPOSE,
            run_id=self._run_id,
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )

    async def run(self, llm: LlmPort, emit: EventSink) -> SideOutput:
        emit("step", "llm", {"step": "request_sent", "purpose": LLM_PURPOSE})
        result = await llm.parse(self.request(), S1LlmReport)
        emit(
            "step",
            "llm",
            {
                "step": "answers",
                "latency_ms": result.latency_ms,
                "refusal": result.refusal,
                "error": result.error,
            },
        )
        usage = result.usage
        usages = (
            CallUsage(
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
            ),
        )
        if result.parsed is None:
            note = result.refusal or f"The model returned no usable answer ({result.error})."
            return SideOutput((), usages, (result.model,), (note,))
        findings = tuple(self._finding(i, f) for i, f in enumerate(result.parsed.findings, 1))
        for finding in findings:
            emit("finding", "llm", {"finding": finding.model_dump(mode="json")})
        emit("step", "llm", {"step": "done", "findings": len(findings)})
        return SideOutput(findings, usages, (result.model,))

    def _finding(self, index: int, raw: LlmFinding) -> Finding:
        span = find_quote(self._docs, raw.quote)
        return Finding(
            id=f"llm:{index:02d}",
            kind=raw.kind,
            doc_id=raw.invoice_id.strip().lower(),
            line_ref=re.sub(r"\s*[,&+]\s*", "+", raw.line_ref.strip()),
            billed=_amount(raw.billed),
            expected=_amount(raw.expected),
            variance=_amount(raw.variance),
            lane="auto",
            evidence=(span,) if span else (),
            traceable=span is not None,
        )
