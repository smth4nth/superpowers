import subprocess
from datetime import datetime, timezone
from pathlib import Path


def _started_at():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fresh_prompt(item, started_at):
    human_input_line = (
        f"\nhuman_input: {item['human_input']}" if item.get("human_input") else ""
    )
    return (
        "[AUTONOMOUS MODE: proceed through all steps without asking for human input or approval. "
        "Make all design decisions based on the task description below.]\n\n"
        f"{item['title']}\n\n"
        f"{item['description']}"
        f"{human_input_line}\n\n"
        f"loop_item_id: {item['id']}\n"
        f"loop_started_at: {started_at}"
    )


def _resume_prompt(item, started_at):
    return (
        "[AUTONOMOUS MODE: proceed through all steps without asking "
        "for human input or approval.]\n\n"
        "Brainstorming is complete. The spec has been written and committed.\n"
        "Proceed with writing-plans, then subagent-driven-development, "
        "then finishing-a-development-branch.\n\n"
        f"loop_item_id: {item['id']}\n"
        f"loop_started_at: {started_at}"
    )


def run(item, codex_cmd="codex"):
    """Launch a Codex session for item.

    Returns:
        0        - success
        -1       - project_dir does not exist
        -2       - codex binary not found or not executable
        non-zero - codex exited with error
    """
    project_dir = str(Path(item["project_dir"]).expanduser())
    if not Path(project_dir).exists():
        return -1

    started_at = _started_at()
    base_flags = [
        "-C", project_dir,
        "--dangerously-bypass-approvals-and-sandbox",
        "--dangerously-bypass-hook-trust",
    ]

    if item.get("session_id"):
        cmd = [
            codex_cmd,
            "exec",
            "resume",
            item["session_id"],
            _resume_prompt(item, started_at),
            *base_flags,
        ]
    else:
        cmd = [
            codex_cmd,
            "exec",
            _fresh_prompt(item, started_at),
            *base_flags,
        ]

    try:
        result = subprocess.run(cmd, cwd=project_dir)
        return result.returncode
    except (FileNotFoundError, PermissionError):
        return -2
