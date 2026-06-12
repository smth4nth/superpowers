import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run(item, claude_cmd="claude"):
    """Launch a claude session for item. Returns exit code (0=ok, -1=bad project_dir)."""
    if not Path(item["project_dir"]).exists():
        return -1

    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    human_input_line = (
        f"\nhuman_input: {item['human_input']}" if item.get("human_input") else ""
    )
    prompt = (
        f"{item['title']}\n\n"
        f"{item['description']}"
        f"{human_input_line}\n\n"
        f"loop_item_id: {item['id']}\n"
        f"loop_started_at: {started_at}"
    )
    result = subprocess.run(
        [claude_cmd, "-p", prompt, "--dangerously-skip-permissions"],
        cwd=item["project_dir"],
    )
    return result.returncode
