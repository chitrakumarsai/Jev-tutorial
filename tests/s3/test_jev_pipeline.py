"""S3 on the Jev side: code finds each quote (fabricated if nowhere), Jev judges whether the
passage holding it supports, contradicts or says nothing about the claim, code gates and notes
a wrong section."""

import asyncio
from typing import Any

import pytest

from jev.domain.documents import Document, DocumentSet
from jev.providers.jev.types import ChoiceQ
from jev.scenarios.s1_reconciliation.documents import load_s1_documents
from jev.scenarios.s3_citation_check.answer_key import load_s3_key
from jev.scenarios.s3_citation_check.documents import load_memo
from jev.scenarios.s3_citation_check.jev_pipeline import JevS3Pipeline
from jev.scenarios.s3_citation_check.locate import locate
from jev.scenarios.s3_citation_check.memo_draft import MemoCitation
from jev.scenarios.s3_citation_check.verdicts import RELATION_VERDICT, RELATIONS
from tests.s1.facts import DATA
from tests.s3.fake_jev import FakeS3Jev

DOCS = load_s1_documents(DATA)
MEMO = load_memo(DATA)
KEY = load_s3_key(DATA)
CITATIONS = {c.id: c for c in MEMO.citations}


def pipeline() -> JevS3Pipeline:
    return JevS3Pipeline(DOCS, MEMO, review_threshold=0.8, run_id="r1")


async def run(fake: FakeS3Jev) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    output = await pipeline().run(fake, lambda type_, side, data: events.append((type_, data)))
    return output, events


def test_a_quote_is_found_where_it_really_is_even_under_a_wrong_section() -> None:
    located = locate(CITATIONS["C1"], DOCS)

    assert located is not None
    assert (located.actual_section, located.section_ok) == ("§3.1", False)
    assert located.passage.startswith("3.1 Line-haul rates.")
    assert DOCS.get("msa").text[located.span.start : located.span.end] == located.span.text


def test_an_invoice_quote_brings_its_rows_and_a_fabricated_quote_is_nowhere() -> None:
    rows = locate(CITATIONS["C4"], DOCS)

    assert rows is not None and rows.section_ok
    assert "| L1 |" in rows.passage and "| L2 |" in rows.passage
    assert locate(CITATIONS["C3"], DOCS) is None


def test_relations_are_three_and_map_onto_citation_verdicts() -> None:
    assert list(RELATIONS) == ["supports", "contradicts", "says_nothing"]
    assert RELATION_VERDICT == {
        "supports": "verified",
        "contradicts": "contradicted",
        "says_nothing": "unsupported",
    }


def test_one_request_per_found_quote_with_the_claim_and_its_passage() -> None:
    requests = pipeline().requests()

    assert [r.purpose for r in requests] == [
        f"s3.citation.{c.id}" for c in MEMO.citations if c.id != "C3"
    ]
    first = next(r for r in requests if r.purpose == "s3.citation.C1")
    assert isinstance(first.state, dict)
    assert first.state["claim"] == CITATIONS["C1"].claim
    assert str(first.state["passage"]).startswith("3.1 Line-haul rates.")
    question = first.questions["relation"]
    assert isinstance(question, ChoiceQ) and list(question.criteria) == list(RELATIONS)


async def test_a_reader_like_the_key_reproduces_every_verdict() -> None:
    fake = FakeS3Jev(KEY)

    output, _ = await run(fake)

    found = {f.id.removeprefix("jev-"): f for f in output.findings}
    assert {cid: f.verdict for cid, f in found.items()} == {
        i.citation_id: i.verdict for i in KEY.items
    }
    assert len(fake.requests) == 9  # the fabricated quote never reaches Jev
    assert all(f.kind == "citation" and f.claim for f in output.findings)


async def test_a_wrong_section_is_noted_but_the_verdict_stands() -> None:
    output, _ = await run(FakeS3Jev(KEY))
    c1 = next(f for f in output.findings if f.id == "jev-C1")

    assert (c1.verdict, c1.lane, c1.line_ref) == ("verified", "auto", "§5.1")
    assert "cited §5.1" in str(c1.review_reason) and "§3.1" in str(c1.review_reason)
    assert c1.evidence and c1.evidence[0].doc_id == "msa"


async def test_a_fabricated_quote_has_no_evidence_and_no_jev_confidence() -> None:
    output, _ = await run(FakeS3Jev(KEY))
    c3 = next(f for f in output.findings if f.id == "jev-C3")

    assert (c3.verdict, c3.evidence, c3.confidence, c3.lane) == ("fabricated", (), None, "auto")


async def test_low_confidence_goes_to_review_with_the_reason() -> None:
    output, _ = await run(FakeS3Jev(KEY, confidences={"C8": 0.55}))
    c8 = next(f for f in output.findings if f.id == "jev-C8")

    assert (c8.lane, c8.verdict) == ("review", "unsupported")
    assert "55% is below 80%" in str(c8.review_reason)


@pytest.mark.parametrize("fault", [{"omitted": {"C7"}}, {"relations": {"C7": "maybe"}}])
async def test_a_missing_or_unknown_answer_goes_to_review_without_a_verdict(
    fault: dict[str, Any],
) -> None:
    output, _ = await run(FakeS3Jev(KEY, **fault))
    c7 = next(f for f in output.findings if f.id == "jev-C7")

    assert (c7.verdict, c7.lane) == (None, "review")


async def test_the_events_the_ui_plays() -> None:
    output, events = await run(FakeS3Jev(KEY))

    steps = [data.get("step", type_) for type_, data in events]
    assert steps[0] == "candidates"
    assert steps.count("request_sent") == steps.count("answers") == 9
    n = len(MEMO.citations)
    assert steps[-(n + 2) :] == ["computed", *["finding"] * n, "gated"]
    assert events[0][1] == {"step": "candidates", "requests": 9, "questions": 9}
    assert len(output.usages) == 9 and output.models == ("jev-1.13.0",)


def _cite(section: str, quote: str, text: str) -> tuple[MemoCitation, DocumentSet]:
    docs = DocumentSet(documents=(Document(doc_id="msa", text=text),))
    return MemoCitation(id="C1", claim="c", quote=quote, doc_id="msa", section=section), docs


def test_a_quote_that_appears_twice_is_taken_from_the_cited_clause() -> None:
    text = "1.1 Fees are due monthly in arrears.\n2.1 Fees are due monthly in arrears.\n"
    citation, docs = _cite("§2.1", "Fees are due monthly in arrears.", text)

    located = locate(citation, docs)

    assert located is not None
    assert (located.actual_section, located.section_ok) == ("§2.1", True)
    assert located.passage.startswith("2.1 ")


@pytest.mark.parametrize("section", ["Section 2.1", "cl. 2.1", "§ 2.1"])
def test_other_ways_of_citing_a_clause_are_understood(section: str) -> None:
    citation, docs = _cite(
        section, "Fees are due monthly in arrears.", "2.1 Fees are due monthly in arrears.\r\n"
    )

    located = locate(citation, docs)

    assert located is not None and located.section_ok
    assert not located.passage.endswith("\r")


class _FailingJev(FakeS3Jev):
    async def evaluate(self, request: Any) -> Any:
        if request.purpose.endswith(".C2"):
            raise RuntimeError("provider down")
        await asyncio.sleep(0.05)
        self.finished.append(request.purpose)
        return await super().evaluate(request)


async def test_one_failed_request_stops_the_others_instead_of_spending_on() -> None:
    fake = _FailingJev(KEY)
    fake.finished = []

    with pytest.raises(RuntimeError, match="provider down"):
        await run(fake)
    await asyncio.sleep(0.15)  # long enough for any request left running to finish

    assert fake.finished == []
