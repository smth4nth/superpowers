import subprocess
import sys
import time
from pathlib import Path


def _spec_committed(project_dir, spec_path):
    """Return True when spec_path no longer appears in git status (i.e. committed)."""
    try:
        result = subprocess.run(
            ["git", "status", "--short", str(spec_path)],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == ""
    except OSError:
        return False


def _wait_for_commit(project_dir, spec_path, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _spec_committed(project_dir, spec_path):
            return
        time.sleep(2)


def run(item, claude_cmd="claude", _claude_dir=None):
    """
    Launch a brainstorming session in two steps:
      1. Seed: claude -p "<title>\\n\\n<description>" (non-interactive) — creates session,
         Claude produces initial thoughts.
      2. Resume: claude --resume <session_id> in a new terminal window (interactive) —
         user sees Claude's response and continues the conversation.

    Returns:
        session_id (str) — spec committed and session captured
        None             — error or user abandoned without writing spec
    """
    project_dir = str(Path(item["project_dir"]).expanduser())
    if not Path(project_dir).exists():
        return None

    specs_dir = Path(project_dir) / "docs" / "superpowers" / "specs"
    specs_before = set(specs_dir.glob("*.md")) if specs_dir.exists() else set()

    claude_dir = Path(_claude_dir) if _claude_dir else Path.home() / ".claude" / "projects"
    sessions_before = set(claude_dir.glob("**/*.jsonl")) if claude_dir.exists() else set()

    # Step 1: seed the session with task context (non-interactive, output suppressed)
    initial_prompt = f"{item['title']}\n\n{item.get('description', '')}"
    try:
        subprocess.run(
            [claude_cmd, "-p", initial_prompt],
            cwd=project_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, PermissionError):
        return None

    sessions_after_seed = set(claude_dir.glob("**/*.jsonl")) if claude_dir.exists() else set()
    new_after_seed = sessions_after_seed - sessions_before
    if not new_after_seed:
        return None
    session_id = Path(sorted(new_after_seed, key=lambda p: p.stat().st_mtime)[-1]).stem

    # Step 2: open interactive window resuming the seeded session
    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                [claude_cmd, "--resume", session_id],
                cwd=project_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            proc = subprocess.Popen(
                [claude_cmd, "--resume", session_id],
                cwd=project_dir,
            )
    except (FileNotFoundError, PermissionError):
        return None

    new_spec = None
    loop_ran = False

    while proc.poll() is None:
        loop_ran = True
        time.sleep(2)
        if specs_dir.exists():
            specs_after = set(specs_dir.glob("*.md"))
            new_specs = specs_after - specs_before
            if new_specs:
                new_spec = sorted(new_specs, key=lambda p: p.stat().st_mtime)[-1]
                _wait_for_commit(project_dir, new_spec)
                proc.terminate()
                break

    # Final check: user may have exited naturally after writing the spec.
    # If loop never ran (process already exited before first poll), treat all
    # current specs as candidates rather than diffing against specs_before.
    if new_spec is None and specs_dir.exists():
        specs_after_loop = set(specs_dir.glob("*.md"))
        candidates = specs_after_loop - specs_before if loop_ran else specs_after_loop
        if candidates:
            new_spec = sorted(candidates, key=lambda p: p.stat().st_mtime)[-1]

    if new_spec is None:
        return None

    return session_id
