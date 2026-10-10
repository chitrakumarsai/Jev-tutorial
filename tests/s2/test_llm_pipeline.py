"""S2 on the LLM side: one structured call; code checks every quote against the addendum."""

from pathlib import Path
from typing import Any

from jev.providers.openai.types import LlmRequest, LlmResult, LlmUsage
from jev.scenarios.s2_clause_review.answer_key import load_s2_key
from jev.scenarios.s2_clause_review.checklist import load_checklist
from jev.scenarios.s2_clause_review.documents import load_s2_documents
from jev.scenarios.s2_clause_review.llm_pipeline import LlmS2Pipeline
from jev.scenarios.s2_clause_review.llm_schema import S2LlmClause, S2LlmReport

DATA = Path(__file__).resolve().parents[2] / "data"
DOCS = load_s2_documents(DATA)
CHECKLIST = load_checklist(DATA)
KEY = load_s2_key(DATA)


class FakeLlm:
    def __init__(self, report: S2LlmReport | None, refusal: str | None = None) -> None:
        self.report, self.refusal = report, refusal
        self.requests: list[LlmRequest] = []

    async def parse(self, request: LlmRequest, schema: type[Any]) -> LlmResult[Any]:
        self.requests.append(request)
        return LlmResult[schema](  # type: ignore[valid-type]
            model="gpt-6-luna-2026-09-01",
            latency_ms=2_000,
            usage=LlmUsage(input_tokens=3_000, output_tokens=1_200),
            parsed=self.report,
            refusal=self.refusal,
        )


def keyed_report(**overrides: dict[str, Any]) -> S2LlmReport:
    """What a perfect auditor would answer, per the approved key, with per-clause overrides."""
    clauses = []
    for item in KEY.items:
        fields: dict[str, Any] = {
            "clause_id": item.clause_id,
            "status": item.status,
            "section": None if item.status == "absent" else "§x",
            "quote": item.quote,
            "risk": item.risk,
            "explanation": "e",
        }
        clauses.append(S2LlmClause(**{**fields, **overrides.get(item.clause_id, {})}))
    return S2LlmReport(clauses=clauses)


def pipeline() -> LlmS2Pipeline:
    return LlmS2Pipeline(DOCS, CHECKLIST, run_id="r1")


async def run(fake: FakeLlm) -> tuple[Any, list[tuple[str, dict[str, Any]]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    output = await pipeline().run(fake, lambda type_, side, data: events.append((type_, data)))
    return output, events


def test_the_prompt_gives_the_checklist_rubrics_and_the_addendum_as_untrusted_data() -> None:
    request = pipeline().request()

    assert "untrusted data" in request.instructions
    for clause in CHECKLIST.clauses:
        assert clause.id in request.input and clause.risk_rubric[3] in request.input
    assert '<document id="addendum">' in request.input


async def test_a_perfect_answer_gives_one_traceable_finding_per_clause() -> None:
    output, _ = await run(FakeLlm(keyed_report()))

    found = {f.kind: f for f in output.findings}
    assert len(found) == len(KEY.items)
    for item in KEY.items:
        finding = found[item.clause_id]
        assert (finding.verdict, finding.risk, finding.traceable) == (item.status, item.risk, True)
    assert found["limitation_of_liability"].line_ref == "L068"
    assert found["breach_notification"].evidence == ()


async def test_an_invented_clause_quote_is_marked_untraceable() -> None:
    invented = "Carrier will notify Customer of any security incident within 72 hours."
    report = keyed_report(
        breach_notification={"status": "present", "quote": invented, "risk": "medium"}
    )

    output, _ = await run(FakeLlm(report))
    breach = next(f for f in output.findings if f.kind == "breach_notification")

    assert (breach.verdict, breach.traceable, breach.evidence) == ("present", False, ())


async def test_unknown_duplicate_and_missing_clauses_are_noted_not_scored_twice() -> None:
    report = keyed_report()
    extra = report.clauses[0].model_copy(update={"clause_id": "no_such_clause"})
    clauses = [*report.clauses[1:], report.clauses[1], extra]  # drops the first, repeats one

    output, _ = await run(FakeLlm(S2LlmReport(clauses=clauses)))

    kinds = [f.kind for f in output.findings]
    assert len(kinds) == len(set(kinds)) == len(KEY.items) - 1
    notes = " ".join(output.notes)
    assert "no_such_clause" in notes
    assert KEY.items[0].clause_id in notes
    assert "more than once" in notes


async def test_a_refusal_is_a_note_and_no_findings() -> None:
    output, events = await run(FakeLlm(None, refusal="I can't help with that."))

    assert output.findings == ()
    assert output.notes == ("I can't help with that.",)
    assert events[-1][1]["step"] == "answers"


async def test_the_events_the_ui_plays() -> None:
    output, events = await run(FakeLlm(keyed_report()))

    steps = [data.get("step", type_) for type_, data in events]
    assert steps == ["request_sent", "answers", *["finding"] * len(KEY.items), "done"]
    assert output.usages[0].output_tokens == 1_200
