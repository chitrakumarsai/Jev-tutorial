"""S3 on the LLM side: one structured call over the memo's citations and the S1 documents,
with the same relation definitions and scoping rule as Jev."""

from typing import Any

from jev.providers.openai.types import LlmRequest, LlmResult, LlmUsage
from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s3_citation_check.answer_key import load_s3_key
from jev.scenarios.s3_citation_check.documents import load_memo
from jev.scenarios.s3_citation_check.llm_pipeline import LlmS3Pipeline
from jev.scenarios.s3_citation_check.llm_schema import S3LlmCitation, S3LlmReport
from jev.scenarios.s3_citation_check.verdicts import RELATIONS
from tests.s1.facts import DATA

DOCS = load_s1_documents(DATA)
MEMO = load_memo(DATA)
KEY = load_s3_key(DATA)


class FakeLlm:
    def __init__(self, report: S3LlmReport | None, refusal: str | None = None) -> None:
        self.report, self.refusal = report, refusal
        self.requests: list[LlmRequest] = []

    async def parse(self, request: LlmRequest, schema: type[Any]) -> LlmResult[Any]:
        self.requests.append(request)
        return LlmResult[schema](  # type: ignore[valid-type]
            model="gpt-6-luna",
            latency_ms=4_000,
            usage=LlmUsage(input_tokens=7_000, output_tokens=900),
            parsed=self.report,
            refusal=self.refusal,
        )


def keyed(**overrides: str) -> S3LlmReport:
    return S3LlmReport(
        citations=[
            S3LlmCitation(
                citation_id=i.citation_id,
                verdict=overrides.get(i.citation_id, i.verdict),  # type: ignore[arg-type]
                reason="r",
            )
            for i in KEY.items
        ]
    )


def pipeline() -> LlmS3Pipeline:
    return LlmS3Pipeline(DOCS, MEMO, run_id="r1")


async def run(fake: FakeLlm) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    output = await pipeline().run(fake, lambda type_, side, data: events.append((type_, data)))
    return output, events


def test_the_prompt_uses_jevs_relation_words_and_scoping_rule_over_untrusted_documents() -> None:
    request = pipeline().request()
    flat = " ".join(request.instructions.split())

    assert all(text in flat for text in RELATIONS.values())
    assert "untrusted data" in flat and "only what the lines holding its quote show" in flat
    for citation in MEMO.citations:
        assert citation.id in request.input and citation.claim in request.input
    for doc in DOCS.documents:
        assert request.input.count(f'<document id="{doc.doc_id}">') == 1


async def test_a_perfect_answer_gives_one_finding_per_citation_with_located_evidence() -> None:
    output, _ = await run(FakeLlm(keyed()))

    verdicts = {f.id.removeprefix("llm-"): f.verdict for f in output.findings}
    assert verdicts == {i.citation_id: i.verdict for i in KEY.items}
    c2 = next(f for f in output.findings if f.id == "llm-C2")
    assert c2.evidence and c2.evidence[0].doc_id == "msa" and c2.claim
    c3 = next(f for f in output.findings if f.id == "llm-C3")
    assert c3.evidence == ()


async def test_unknown_duplicate_and_missing_citations_become_notes() -> None:
    report = keyed()
    extra = report.citations[0].model_copy(update={"citation_id": "C99"})
    lower = report.citations[1].model_copy(update={"citation_id": " c2 "})
    cits = [*report.citations[1:], lower, extra]  # drops C1, repeats C2 (as " c2 ")

    output, _ = await run(FakeLlm(S3LlmReport(citations=cits)))

    ids = [f.id for f in output.findings]
    assert len(ids) == len(set(ids)) == len(MEMO.citations) - 1
    notes = " ".join(output.notes)
    assert "C99" in notes and "C1" in notes and "more than once" in notes


async def test_a_refusal_is_a_note_and_no_findings() -> None:
    output, events = await run(FakeLlm(None, refusal="I can't help with that."))

    assert (output.findings, output.notes) == ((), ("I can't help with that.",))
    assert events[-1][1]["step"] == "answers"


async def test_the_events_the_ui_plays() -> None:
    output, events = await run(FakeLlm(keyed()))

    steps = [data.get("step", type_) for type_, data in events]
    n = len(MEMO.citations)
    assert steps == ["request_sent", "answers", *["finding"] * n, "done"]
    assert output.usages[0].output_tokens == 900
