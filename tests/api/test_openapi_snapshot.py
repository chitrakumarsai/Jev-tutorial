"""The web client's types are generated from web/openapi.json, so it must match the live app."""

import json
from pathlib import Path

from jev.cli import main, openapi_json

SNAPSHOT = Path(__file__).parents[2] / "web" / "openapi.json"


def test_committed_snapshot_matches_the_app() -> None:
    assert SNAPSHOT.read_text(encoding="utf-8") == openapi_json(), (
        "web/openapi.json is stale: run `uv run python -m jev.cli openapi` "
        "then `npm --prefix web run gen:api`"
    )


def test_export_is_deterministic_and_ends_with_a_newline() -> None:
    first = openapi_json()

    assert first == openapi_json()
    assert first.endswith("}\n")
    assert json.loads(first)["info"]["title"]


def test_cli_writes_the_snapshot(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"

    assert main(["openapi", "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == openapi_json()
