import subprocess
import sys
import time
from pathlib import Path


def _spec_committed(project_dir, spec_path):
    """Return True when spec_path no longer appears in git status."""
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


def run(item, codex_cmd="codex", _codex_dir=None):
    """Launch an interactive Codex brainstorming session.

    Returns:
        session_id (str) - spec committed and session captured
        None             - error or user abandoned without writing spec
    """
    project_dir = str(Path(item["project_dir"]).expanduser())
    if not Path(project_dir).exists():
        return None

    specs_dir = Path(project_dir) / "docs" / "superpowers" / "specs"
    specs_before = set(specs_dir.glob("*.md")) if specs_dir.exists() else set()

    codex_dir = Path(_codex_dir) if _codex_dir else Path.home() / ".codex" / "sessions"
    sessions_before = set(codex_dir.glob("**/*.jsonl")) if codex_dir.exists() else set()

    prompt = f"{item['title']}\n\n{item.get('description', '')}"
    cmd = [codex_cmd, prompt, "-C", project_dir]

    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                cmd,
                cwd=project_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            proc = subprocess.Popen(cmd, cwd=project_dir)
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

    if new_spec is None and specs_dir.exists():
        specs_after_loop = set(specs_dir.glob("*.md"))
        candidates = specs_after_loop - specs_before if loop_ran else specs_after_loop
        if candidates:
            new_spec = sorted(candidates, key=lambda p: p.stat().st_mtime)[-1]

    if new_spec is None:
        return None

    sessions_after = set(codex_dir.glob("**/*.jsonl")) if codex_dir.exists() else set()
    new_sessions = sessions_after - sessions_before
    if not new_sessions:
        return None
    return Path(sorted(new_sessions, key=lambda p: p.stat().st_mtime)[-1]).stem
