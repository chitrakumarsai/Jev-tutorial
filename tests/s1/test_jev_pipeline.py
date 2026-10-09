"""Jev pipeline: typed judgments over candidates, maths in code, uncertain items to review."""

from typing import Any

from jev.scenarios.s1_reconciliation.jev_pipeline import JevS1Pipeline
from jev.scoring.scorecard import score
from tests.s1.facts import DOCS
from tests.s1.fake_jev import FakeJev
from tests.s1.test_reconcile import KEY

CONTRACT = "s1.contract"


class Events:
    def __init__(self) -> None:
        self.items: list[tuple[str, str | None, dict[str, Any]]] = []

    def __call__(self, kind: str, side: str | None, data: dict[str, Any]) -> None:
        self.items.append((kind, side, data))


def pipeline() -> JevS1Pipeline:
    return JevS1Pipeline(DOCS, review_threshold=0.8, run_id="run-1")


async def run(fake: FakeJev, events: Events | None = None):  # type: ignore[no-untyped-def]
    return await pipeline().run(fake, events or Events())


def test_requests_cover_the_contract_and_every_invoice() -> None:
    requests = pipeline().requests()

    assert [r.purpose for r in requests] == [CONTRACT] + [
        f"s1.invoice.inv-2026-{m:02d}" for m in range(1, 13)
    ]
    contract = requests[0]
    assert "zone_a_rate" in contract.questions and "zone_a_rate__rev" in contract.questions
    assert "late_fee_pct__rev" not in contract.questions  # twins only on the key picks
    assert all("none" in q.criteria for q in contract.questions.values())  # type: ignore[union-attr]
    inv10 = requests[10].questions
    assert {"kind_L1", "invoice_date", "dup_L4_L5"} <= set(inv10)
    inv5 = requests[5].questions
    assert {"paid_L5", "refinv_L5", "base_L5"} <= set(inv5)


def test_twin_lists_options_in_reverse_order() -> None:
    q = pipeline().requests()[0].questions
    forward = list(q["discount_pct"].criteria)  # type: ignore[union-attr]
    backward = list(q["discount_pct__rev"].criteria)  # type: ignore[union-attr]

    assert forward[:-1] == list(reversed(backward[:-1])) and forward[-1] == backward[-1] == "none"


async def test_perfect_judgments_reproduce_the_answer_key() -> None:
    output = await run(FakeJev())

    card = score(output.findings, KEY)
    assert (card.correct, card.of, card.false_positives) == (14, 14, ())
    assert card.total_variance_exact
    assert all(f.lane == "auto" for f in output.findings)
    assert len(output.usages) == 13


async def test_every_finding_carries_verbatim_evidence() -> None:
    output = await run(FakeJev())

    for finding in output.findings:
        assert finding.evidence, finding.id
        for span in finding.evidence:
            assert DOCS.get(span.doc_id).text[span.start : span.end] == span.text


async def test_low_confidence_line_kind_sends_its_findings_to_review() -> None:
    fake = FakeJev(confidences={("s1.invoice.inv-2026-04", "kind_L3"): 0.55})

    output = await run(fake)

    flagged = [f for f in output.findings if f.doc_id == "inv-2026-04"]
    assert flagged and all(f.lane == "review" for f in flagged)
    assert "low confidence" in (flagged[0].review_reason or "")
    assert score(output.findings, KEY).correct_in_review == 1


async def test_order_twin_disagreement_sends_dependent_findings_to_review() -> None:
    fake = FakeJev(choices={(CONTRACT, "fuel_cap_pct__rev"): "1.5%"})

    output = await run(fake)

    cap = [f for f in output.findings if f.kind == "surcharge_over_cap"]
    assert cap and cap[0].lane == "review"
    assert "option order" in (cap[0].review_reason or "")


async def test_missing_contract_term_yields_no_guessed_findings() -> None:
    events = Events()

    output = await run(FakeJev(choices={(CONTRACT, "discount_pct"): "none"}), events)

    assert output.findings == ()
    assert any("discount_pct" in note for note in output.notes)


async def test_duplicate_needs_jev_to_confirm_it() -> None:
    output = await run(FakeJev(nouls={("s1.invoice.inv-2026-10", "dup_L4_L5"): 0.1}))

    assert not [f for f in output.findings if f.kind == "duplicate_line"]


async def test_pipeline_emits_its_steps_in_order() -> None:
    events = Events()

    await run(FakeJev(), events)

    steps = [d["step"] for kind, side, d in events.items if kind == "step"]
    assert steps[0] == "candidates" and steps[-1] == "gated"
    assert "answers" in steps and "computed" in steps
    assert all(side == "jev" for _, side, _ in events.items)
    assert sum(1 for kind, _, _ in events.items if kind == "finding") == 14
