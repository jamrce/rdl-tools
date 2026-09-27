"""The Claude Code PreToolUse hook that keeps agents to read-only git and gh commands."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the hook runs only in the Linux devcontainer")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SETTINGS = PROJECT_ROOT / ".claude" / "settings.json"
HOOK = PROJECT_ROOT / ".claude" / "hooks" / "block-git-writes.sh"


def run_hook(command: str) -> subprocess.CompletedProcess[str]:
    # The shape Claude Code sends, since the hook scans the whole payload.
    payload = {
        "session_id": "s",
        "transcript_path": "/home/vscode/.claude/projects/-workspace/s.jsonl",
        "cwd": "/workspace",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command, "description": "Run a command"},
    }
    return subprocess.run(
        [shutil.which("sh") or "sh", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def denied_prefixes() -> list[str]:
    deny = json.loads(SETTINGS.read_text(encoding="utf-8"))["permissions"]["deny"]
    return [rule.removeprefix("Bash(").removesuffix(":*)") for rule in deny]


@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git -C . commit -m wip",
        'sh -c "git push origin main"',
        "cd src && git reset --hard",
        "/usr/bin/git stash",
        "git --no-pager -c user.name=x commit -m wip",
        "git --git-dir .git push",
        "echo $(git checkout main)",
        "ls\ngit push",
        "gh pr create --fill",
        "gh issue comment 11 --body hi",
        "gh auth token",
    ],
)
def test_a_write_command_is_blocked_wherever_it_appears(command: str):
    result = run_hook(command)
    assert result.returncode == 2
    assert "Blocked:" in result.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git status --short",
        "git log --grep commit",
        "git rev-parse --abbrev-ref HEAD",
        "git diff main -- src",
        "gh issue view 11 --comments",
        "gh api repos/jamrce/rdl-tools/issues/11/dependencies/blocked_by",
        "grep -rn push src",
        "cat .gitignore",
    ],
)
def test_a_read_command_is_allowed(command: str):
    result = run_hook(command)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("prefix", denied_prefixes())
def test_every_denied_prefix_is_blocked_inside_a_subshell(prefix: str):
    result = run_hook(f'sh -c "{prefix} x"')
    assert result.returncode == 2
    assert "Blocked:" in result.stderr


def test_the_hook_runs_before_every_bash_call():
    pre_tool_use = json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]
    commands = [h["command"] for entry in pre_tool_use if entry["matcher"] == "Bash" for h in entry["hooks"]]
    assert any("block-git-writes.sh" in c for c in commands)
