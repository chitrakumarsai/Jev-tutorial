"""The scenario registry: each scenario is looked up by id, and S1 is unchanged behind it.

These check the wiring; S1's golden replays (tests/golden) are what prove its behaviour."""

import re
from dataclasses import replace

import pytest

from jev.config import Settings
from jev.replay.models import ID_PATTERN
from jev.scenarios.registry import SCENARIOS, get_scenario
from jev.scenarios.s1_reconciliation.documents import SCENARIO_ID, load_s1_documents
from jev.scenarios.s1_reconciliation.jev_pipeline import JevS1Pipeline
from jev.scenarios.s1_reconciliation.llm_pipeline import INSTRUCTIONS, LlmS1Pipeline
from jev.scenarios.s1_reconciliation.llm_schema import S1LlmReport
from tests.s1.facts import DATA


def test_lists_s1_first_with_its_title_and_description() -> None:
    first = SCENARIOS[0]

    assert first.id == SCENARIO_ID
    assert first.title == "Contract-to-invoice reconciliation"
    assert "Northwind Logistics" in first.description


def test_ids_and_aliases_are_unique_and_safe_as_folder_names() -> None:
    names = [name for spec in SCENARIOS for name in (spec.id, spec.alias)]

    assert len(names) == len(set(names))
    assert all(re.fullmatch(ID_PATTERN, name) for name in names)


def test_looks_a_scenario_up_by_id_or_alias() -> None:
    assert get_scenario(SCENARIO_ID) is SCENARIOS[0]
    assert get_scenario("s1") is SCENARIOS[0]
    assert get_scenario("no_such_scenario") is None


@pytest.mark.parametrize("bad", ["", "../escape", "has space", "x" * 65])
def test_a_spec_with_an_unsafe_id_is_refused(bad: str) -> None:
    with pytest.raises(ValueError, match="must match"):
        replace(SCENARIOS[0], id=bad)


def test_s1_spec_carries_the_llm_prompt_and_schema() -> None:
    spec = get_scenario(SCENARIO_ID)
    assert spec is not None

    assert spec.llm_instructions == INSTRUCTIONS
    assert spec.llm_schema is S1LlmReport


def test_s1_spec_builds_the_same_requests_as_the_s1_pipelines() -> None:
    spec = get_scenario(SCENARIO_ID)
    assert spec is not None
    docs = spec.load_documents(DATA)

    settings = Settings(_env_file=None, review_threshold=0.8)  # type: ignore[call-arg]
    jev, llm = spec.build_pipelines(docs, settings, "run-1")

    direct_docs = load_s1_documents(DATA)
    assert (
        jev.requests()
        == JevS1Pipeline(direct_docs, review_threshold=0.8, run_id="run-1").requests()
    )
    assert llm.request() == LlmS1Pipeline(direct_docs, run_id="run-1").request()


def test_s1_spec_loads_a_scorer_bound_to_its_answer_key() -> None:
    spec = get_scenario(SCENARIO_ID)
    assert spec is not None

    card = spec.load_scorer(DATA)([])

    assert (card.correct, card.of) == (0, 14)
    assert card.variance is not None


def test_s1_spec_validates_its_data() -> None:
    spec = get_scenario(SCENARIO_ID)
    assert spec is not None

    assert spec.validate_data(DATA) == []


def test_a_spec_can_be_copied_under_another_id() -> None:
    spec = get_scenario(SCENARIO_ID)
    assert spec is not None

    copy = replace(spec, id="s1_copy", title="Copy")

    assert (copy.id, copy.title, spec.id) == ("s1_copy", "Copy", SCENARIO_ID)
