"""Replay: record real results once, then re-run the real pipeline against them offline."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from jev.providers.jev.types import ChoiceA, JevRequest, JevResult, NoulQ, Usage
from jev.providers.openai.types import LlmRequest, LlmResult, LlmUsage
from jev.replay.clients import (
    RecordingJevClient,
    RecordingLlmClient,
    ReplayJevClient,
    ReplayLlmClient,
    ReplayStaleError,
)
from jev.replay.hashing import request_hash
from jev.replay.models import Recording
from jev.replay.store import FileReplayStore, ReplayStoreError


class Answer(BaseModel):
    total: str


class FakeJev:
    def __init__(self) -> None:
        self.calls = 0

    async def evaluate(self, request: JevRequest) -> JevResult:
        self.calls += 1
        return JevResult(
            model="jev-1.13.0",
            latency_ms=140 + self.calls,
            choices={
                "pick": ChoiceA(choice="a", probabilities={"a": 0.9, "b": 0.1}, confidence=0.8)
            },
            scores={},
            nouls={},
            usage=Usage(input_tokens=100, output_tokens=5),
        )


class FakeLlm:
    async def parse(self, request: LlmRequest, schema: type[Answer]) -> LlmResult[Answer]:
        return LlmResult[Answer](
            model="gpt-6-luna-2026-09-01",
            latency_ms=2_300,
            usage=LlmUsage(input_tokens=1_000, output_tokens=400),
            parsed=schema(total="98510.71"),
        )


def jev_request(text: str = "Is this urgent?", run_id: str = "r1") -> JevRequest:
    return JevRequest(
        state={"doc": "x"}, questions={"q": NoulQ(instructions=text)}, purpose="t", run_id=run_id
    )


def llm_request(run_id: str = "r1") -> LlmRequest:
    return LlmRequest(instructions="i", input="docs", purpose="t", run_id=run_id)


def test_hash_ignores_key_order_but_not_content() -> None:
    assert request_hash({"a": 1, "b": [1, 2]}) == request_hash({"b": [1, 2], "a": 1})
    assert request_hash({"a": 1}) != request_hash({"a": 2})
    assert len(request_hash({})) == 64


async def test_jev_record_then_replay_round_trip(tmp_path: Path) -> None:
    recorder = RecordingJevClient(FakeJev(), model="jev-latest")
    live = await recorder.evaluate(jev_request())
    store = FileReplayStore(tmp_path)
    recording = Recording.create(
        "s1_reconciliation", jev_model="jev-latest", llm_model="gpt-6-luna", calls=recorder.calls
    )
    store.save(recording)

    loaded = store.load("s1_reconciliation", recording.id)
    replayed = await ReplayJevClient(loaded).evaluate(jev_request(run_id="a-later-run"))

    assert replayed == live
    assert loaded.calls[0].provider == "typesafe"
    assert loaded.calls[0].purpose == "t"


async def test_llm_record_then_replay_round_trip(tmp_path: Path) -> None:
    recorder = RecordingLlmClient(FakeLlm(), model="gpt-6-luna")
    live = await recorder.parse(llm_request(), Answer)
    recording = Recording.create(
        "s1_reconciliation", jev_model="jev-latest", llm_model="gpt-6-luna", calls=recorder.calls
    )
    FileReplayStore(tmp_path).save(recording)

    loaded = FileReplayStore(tmp_path).load("s1_reconciliation", recording.id)
    replayed = await ReplayLlmClient(loaded).parse(llm_request(run_id="later"), Answer)

    assert replayed == live
    assert replayed.parsed == Answer(total="98510.71")


async def test_changed_request_fails_loudly_instead_of_calling_live() -> None:
    recorder = RecordingJevClient(FakeJev(), model="jev-latest")
    await recorder.evaluate(jev_request("Is this urgent?"))
    recording = Recording.create(
        "s1", jev_model="jev-latest", llm_model="gpt-6-luna", calls=recorder.calls
    )

    with pytest.raises(ReplayStaleError, match="re-record"):
        await ReplayJevClient(recording).evaluate(jev_request("Is this overdue?"))


async def test_repeated_identical_requests_replay_in_recorded_order() -> None:
    recorder = RecordingJevClient(FakeJev(), model="jev-latest")
    first = await recorder.evaluate(jev_request())
    second = await recorder.evaluate(jev_request())
    recording = Recording.create(
        "s1", jev_model="jev-latest", llm_model="gpt-6-luna", calls=recorder.calls
    )
    replay = ReplayJevClient(recording)

    assert await replay.evaluate(jev_request()) == first
    assert await replay.evaluate(jev_request()) == second
    with pytest.raises(ReplayStaleError):
        await replay.evaluate(jev_request())


async def test_wrong_provider_entries_are_not_served() -> None:
    recorder = RecordingLlmClient(FakeLlm(), model="gpt-6-luna")
    await recorder.parse(llm_request(), Answer)
    recording = Recording.create(
        "s1", jev_model="jev-latest", llm_model="gpt-6-luna", calls=recorder.calls
    )

    with pytest.raises(ReplayStaleError):
        await ReplayJevClient(recording).evaluate(jev_request())


def test_store_lists_recordings_newest_first(tmp_path: Path) -> None:
    store = FileReplayStore(tmp_path)
    older = Recording.create(
        "s1", jev_model="j", llm_model="l", calls=(), recorded_at="2026-10-01T00:00:00+00:00"
    )
    newer = Recording.create(
        "s1", jev_model="j", llm_model="l", calls=(), recorded_at="2026-10-09T00:00:00+00:00"
    )
    store.save(older)
    store.save(newer)

    assert [m.id for m in store.list_recordings("s1")] == [newer.id, older.id]
    assert store.list_recordings("s2") == []


@pytest.mark.parametrize("bad_id", ["../etc/passwd", "a/b", "", "x" * 200, "ok id"])
def test_ids_cannot_escape_the_store(tmp_path: Path, bad_id: str) -> None:
    store = FileReplayStore(tmp_path)

    with pytest.raises(ReplayStoreError):
        store.load("s1", bad_id)
    with pytest.raises(ReplayStoreError):
        store.load(bad_id, "abc")


def test_corrupt_or_missing_recordings_raise_store_errors(tmp_path: Path) -> None:
    store = FileReplayStore(tmp_path)
    (tmp_path / "s1").mkdir()
    (tmp_path / "s1" / "broken.json").write_text("{not json")

    with pytest.raises(ReplayStoreError, match="unreadable"):
        store.load("s1", "broken")
    with pytest.raises(ReplayStoreError, match="not found"):
        store.load("s1", "missing")


def test_id_with_trailing_newline_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ReplayStoreError):
        FileReplayStore(tmp_path).load("s1", "abc\n")


def test_recording_filed_under_the_wrong_name_is_rejected(tmp_path: Path) -> None:
    store = FileReplayStore(tmp_path)
    recording = Recording.create("s1", jev_model="j", llm_model="l", calls=())
    path = store.save(recording)
    path.rename(path.with_name("renamed.json"))

    with pytest.raises(ReplayStoreError, match="does not match"):
        store.load("s1", "renamed")


def test_failed_save_leaves_no_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os as os_module

    store = FileReplayStore(tmp_path)
    recording = Recording.create("s1", jev_model="j", llm_model="l", calls=())

    def boom(src: str, dst: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os_module, "replace", boom)
    with pytest.raises(OSError):
        store.save(recording)

    assert list((tmp_path / "s1").glob("*.tmp")) == []
