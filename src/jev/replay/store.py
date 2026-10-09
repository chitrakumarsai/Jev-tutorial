"""File-based recording store: <root>/<scenario_id>/<recording_id>.json."""

import os
import re
import tempfile
from pathlib import Path

from pydantic import ValidationError

from jev.replay.models import ID_PATTERN, Recording, RecordingMeta

_ID_RE = re.compile(ID_PATTERN)


class ReplayStoreError(RuntimeError):
    """A recording is missing, unreadable, or was addressed with an unsafe id."""


def _safe(identifier: str) -> str:
    if not _ID_RE.fullmatch(identifier):
        raise ReplayStoreError(f"Invalid recording or scenario id: {identifier!r}")
    return identifier


class FileReplayStore:
    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, scenario_id: str, recording_id: str) -> Path:
        return self._root / _safe(scenario_id) / f"{_safe(recording_id)}.json"

    def save(self, recording: Recording) -> Path:
        path = self._path(recording.scenario_id, recording.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(recording.model_dump_json(indent=2) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)  # atomic: never leave a half-written recording
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return path

    def load(self, scenario_id: str, recording_id: str) -> Recording:
        path = self._path(scenario_id, recording_id)
        if not path.is_file():
            raise ReplayStoreError(f"Recording {scenario_id}/{recording_id} not found")
        try:
            recording = Recording.model_validate_json(path.read_text(encoding="utf-8"))
        except (ValidationError, UnicodeDecodeError) as exc:
            raise ReplayStoreError(f"Recording {scenario_id}/{recording_id} is unreadable") from exc
        if (recording.scenario_id, recording.id) != (scenario_id, recording_id):
            raise ReplayStoreError(
                f"Recording file {scenario_id}/{recording_id} does not match its contents"
            )
        return recording

    def list_recordings(self, scenario_id: str) -> list[RecordingMeta]:
        folder = self._root / _safe(scenario_id)
        if not folder.is_dir():
            return []
        metas = [self.load(scenario_id, p.stem).meta() for p in folder.glob("*.json")]
        return sorted(metas, key=lambda m: m.recorded_at, reverse=True)
