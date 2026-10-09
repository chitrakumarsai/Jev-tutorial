"""The PreToolUse guard protects API keys and the $5-per-key budget."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

GUARD = Path(__file__).resolve().parents[2] / "scripts" / "hooks" / "pre_tool_guard.sh"

pytestmark = pytest.mark.skipif(shutil.which("jq") is None, reason="guard requires jq")


def decision(payload: dict[str, object] | str) -> str:
    """Run the guard and return its decision: 'deny', 'ask' or 'allow' (no output)."""
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    result = subprocess.run(  # noqa: S603 - fixed local script, test-controlled input
        [str(GUARD)], input=stdin, capture_output=True, text=True, check=True
    )
    if not result.stdout.strip():
        return "allow"
    return str(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"])


def file_tool(tool: str, path: str) -> dict[str, object]:
    return {"tool_name": tool, "tool_input": {"file_path": path}}


def bash(command: str) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


@pytest.mark.parametrize("tool", ["Read", "Edit", "MultiEdit", "Write"])
@pytest.mark.parametrize("name", [".env", ".env.local", ".env.staging", ".env.bak", ".ENV"])
def test_file_tools_cannot_touch_dotenv_files(tool: str, name: str) -> None:
    assert decision(file_tool(tool, f"/repo/{name}")) == "deny"


@pytest.mark.parametrize("tool", ["Read", "Edit", "Write"])
def test_env_example_and_source_files_are_allowed(tool: str) -> None:
    assert decision(file_tool(tool, "/repo/.env.example")) == "allow"
    assert decision(file_tool(tool, "/repo/src/jev/config.py")) == "allow"
    assert decision(file_tool(tool, "/repo/.venv/bin/python")) == "allow"


def test_notebook_edits_on_dotenv_are_denied() -> None:
    payload = {"tool_name": "NotebookEdit", "tool_input": {"notebook_path": "/repo/.env"}}
    assert decision(payload) == "deny"


@pytest.mark.parametrize(
    "tool_input",
    [
        {"pattern": "KEY", "path": ".env"},
        {"pattern": "KEY", "glob": ".env*"},
        {"pattern": "**/.env"},
    ],
)
def test_search_tools_cannot_read_dotenv(tool_input: dict[str, str]) -> None:
    assert decision({"tool_name": "Grep", "tool_input": tool_input}) == "deny"
    assert decision({"tool_name": "Glob", "tool_input": tool_input}) == "deny"


def test_search_of_source_is_allowed() -> None:
    assert (
        decision({"tool_name": "Grep", "tool_input": {"pattern": "def ", "path": "src"}}) == "allow"
    )


@pytest.mark.parametrize(
    "command",
    [
        "cat .env",
        "grep KEY ./.env | head",
        "cp .env.local /tmp/x",
        "source .env",
        "printenv",
        "env | dotenv",
    ],
)
def test_shell_access_to_secrets_is_denied(command: str) -> None:
    assert decision(bash(command)) == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "uv run python -m jev.cli record s1",
        "uv run jev record s1",
        "LIVE_ENABLED=true uv run uvicorn jev.api.app:create_app --factory",
        'LIVE_ENABLED="TRUE" make demo',
        "LIVE_ENABLED=1 uv run pytest",
        "curl https://api.openai.com/v1/models",
        "curl https://api.typesafe.ai/v1/systemone",
    ],
)
def test_live_spend_requires_approval(command: str) -> None:
    assert decision(bash(command)) == "ask"


@pytest.mark.parametrize(
    "command",
    ["uv run pytest -q", "cat .env.example", "ls .venv/bin", "LIVE_ENABLED=false uv run pytest"],
)
def test_ordinary_commands_are_allowed(command: str) -> None:
    assert decision(bash(command)) == "allow"


@pytest.mark.parametrize("stdin", ["", "not json", "{}"])
def test_unparseable_input_fails_closed(stdin: str) -> None:
    assert decision(stdin) == "deny"
