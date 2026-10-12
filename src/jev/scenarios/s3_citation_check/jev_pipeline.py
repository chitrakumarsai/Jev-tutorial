"""S3 on the Jev side (TypeSafe's citation-check recipe): code finds each quote first, and a
quote that is nowhere is fabricated without asking Jev. For every other citation one Jev request
judges whether the passage holding the quote supports, contradicts or says nothing about the
claim. Code gates on confidence and notes a cited section that does not hold the quote."""

import asyncio
from dataclasses import dataclass

from pydantic import JsonValue

from jev.domain.documents import DocumentSet
from jev.domain.findings import CitationVerdict, Finding
from jev.providers.jev.port import JevPort
from jev.providers.jev.types import ChoiceQ, Description, JevRequest, JevResult
from jev.scenarios.base import EventSink, SideOutput
from jev.scenarios.s3_citation_check.locate import Located, locate
from jev.scenarios.s3_citation_check.memo_draft import MemoCitation, MemoDraft
from jev.scenarios.s3_citation_check.verdicts import RELATION_VERDICT, RELATIONS
from jev.scoring.metrics import CallUsage

PURPOSE_PREFIX = "s3.citation."
MAX_CONCURRENCY = 4  # as S1
_OPTIONS: dict[str, Description | None] = dict(RELATIONS.items())


def citation_request(citation: MemoCitation, located: Located, run_id: str) -> JevRequest:
    state: dict[str, JsonValue] = {"claim": citation.claim, "passage": located.passage}
    question = ChoiceQ(
        instructions="How does the `passage` relate to the `claim`?", criteria=_OPTIONS
    )
    return JevRequest(
        state=state,
        questions={"relation": question},
        purpose=f"{PURPOSE_PREFIX}{citation.id}",
        run_id=run_id,
    )


@dataclass(frozen=True)
class _Judged:
    verdict: CitationVerdict | None
    confidence: float | None
    reasons: tuple[str, ...]  # send it to review
    notes: tuple[str, ...]  # shown, but no review


def _judge(result: JevResult, located: Located, cited: str, threshold: float) -> _Judged:
    notes: tuple[str, ...] = ()
    if not located.section_ok and located.actual_section:
        notes = (f"cited {cited}, but the quote is in {located.actual_section}",)
    answer = result.choices.get("relation")
    if answer is None or answer.choice not in RELATION_VERDICT:
        return _Judged(None, None, ("Jev gave no readable answer on this citation",), notes)
    reasons: tuple[str, ...] = ()
    if answer.confidence < threshold:
        reasons = (f"relation {answer.confidence:.0%} is below {threshold:.0%}",)
    return _Judged(RELATION_VERDICT[answer.choice], answer.confidence, reasons, notes)


def _finding(citation: MemoCitation, located: Located | None, judged: _Judged | None) -> Finding:
    if located is None or judged is None:  # fabricated: decided by code, no Jev call
        return Finding(
            id=f"jev-{citation.id}",
            kind="citation",
            doc_id=citation.doc_id,
            line_ref=citation.section,
            verdict="fabricated",
            claim=citation.claim,
            review_reason=f"quote not found in {citation.doc_id}",
        )
    text = "; ".join((*judged.notes, *judged.reasons))
    return Finding(
        id=f"jev-{citation.id}",
        kind="citation",
        doc_id=citation.doc_id,
        line_ref=citation.section,
        verdict=judged.verdict,
        claim=citation.claim,
        confidence=judged.confidence,
        lane="review" if judged.reasons else "auto",
        review_reason=text or None,
        evidence=(located.span,),
    )


class JevS3Pipeline:
    def __init__(
        self, documents: DocumentSet, memo: MemoDraft, *, review_threshold: float, run_id: str
    ) -> None:
        self._memo = memo
        self._threshold = review_threshold
        self._located = {c.id: locate(c, documents) for c in memo.citations}
        self._requests = {
            c.id: citation_request(c, found, run_id)
            for c in memo.citations
            if (found := self._located[c.id]) is not None
        }

    def requests(self) -> list[JevRequest]:
        return list(self._requests.values())

    async def run(self, jev: JevPort, emit: EventSink) -> SideOutput:
        n = len(self._requests)
        emit("step", "jev", {"step": "candidates", "requests": n, "questions": n})
        results = await self._ask_all(jev, emit)
        findings = tuple(self._finding_for(c, results) for c in self._memo.citations)
        emit("step", "jev", {"step": "computed", "findings": len(findings)})
        for finding in findings:
            emit("finding", "jev", {"finding": finding.model_dump(mode="json")})
        emit("step", "jev", {"step": "gated", "review": sum(f.lane == "review" for f in findings)})
        usages = tuple(
            CallUsage(input_tokens=r.usage.input_tokens, output_tokens=r.usage.output_tokens)
            for r in results.values()
        )
        return SideOutput(findings, usages, tuple(sorted({r.model for r in results.values()})))

    def _finding_for(self, citation: MemoCitation, results: dict[str, JevResult]) -> Finding:
        located = self._located[citation.id]
        result = results.get(citation.id)
        judged = (
            _judge(result, located, citation.section, self._threshold)
            if located is not None and result is not None
            else None
        )
        return _finding(citation, located, judged)

    async def _ask_all(self, jev: JevPort, emit: EventSink) -> dict[str, JevResult]:
        gate = asyncio.Semaphore(MAX_CONCURRENCY)

        async def ask(citation_id: str, request: JevRequest) -> tuple[str, JevResult]:
            async with gate:
                emit(
                    "step",
                    "jev",
                    {"step": "request_sent", "purpose": request.purpose, "questions": 1},
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
                    },
                )
                return citation_id, result

        # A TaskGroup cancels the other requests if one fails, so nothing more is spent.
        try:
            async with asyncio.TaskGroup() as group:
                tasks = [group.create_task(ask(cid, r)) for cid, r in self._requests.items()]
        except ExceptionGroup as failed:  # surface the provider's own error, as gather did
            raise failed.exceptions[0] from None
        return dict(task.result() for task in tasks)
