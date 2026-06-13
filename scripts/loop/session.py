import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run(item, claude_cmd="claude"):
    """Launch a claude session for item.

    Returns:
        0        — success
        -1       — project_dir does not exist
        -2       — claude binary not found or not executable
        non-zero — claude exited with error
    """
    if not Path(item["project_dir"]).expanduser().exists():
        return -1

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if item.get("session_id"):
        prompt = (
            "[AUTONOMOUS MODE: proceed through all steps without asking "
            "for human input or approval.]\n\n"
            "Brainstorming is complete. The spec has been written and committed.\n"
            "Proceed with writing-plans, then subagent-driven-development, "
            "then finishing-a-development-branch.\n\n"
            f"loop_item_id: {item['id']}\n"
            f"loop_started_at: {started_at}"
        )
        cmd = [
            claude_cmd,
            "--resume", item["session_id"],
            "-p", prompt,
            "--dangerously-skip-permissions",
        ]
    else:
        human_input_line = (
            f"\nhuman_input: {item['human_input']}" if item.get("human_input") else ""
        )
        prompt = (
            f"[AUTONOMOUS MODE: proceed through all steps without asking for human input or approval. "
            f"Make all design decisions based on the task description below.]\n\n"
            f"{item['title']}\n\n"
            f"{item['description']}"
            f"{human_input_line}\n\n"
            f"loop_item_id: {item['id']}\n"
            f"loop_started_at: {started_at}"
        )
        cmd = [claude_cmd, "-p", prompt, "--dangerously-skip-permissions"]

    try:
        result = subprocess.run(cmd, cwd=item["project_dir"])
        return result.returncode
    except (FileNotFoundError, PermissionError):
        return -2
