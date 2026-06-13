import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _make_win_launch_script(item, claude_cmd):
    """Write a temp PowerShell script that prints task context then launches claude."""
    title = item.get("title", "")
    description = item.get("description", "")
    # PS here-strings end with '@' at column 0 — escape that edge case
    title_safe = title.replace("'@", "' @")
    desc_safe = description.replace("'@", "' @")
    # Quote claude_cmd for PowerShell call operator
    cmd_quoted = f"'{claude_cmd}'" if " " in claude_cmd else claude_cmd

    script = f"""\
$title = @'
{title_safe}
'@
$desc = @'
{desc_safe}
'@
$host.UI.RawUI.WindowTitle = "Brainstorm: $($title.Trim())"
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host "  BRAINSTORM TASK" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host $title.Trim() -ForegroundColor Yellow
Write-Host ""
Write-Host $desc.Trim()
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""
& {cmd_quoted}
"""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".ps1", delete=False, encoding="utf-8-sig"
    )
    f.write(script)
    f.close()
    return f.name


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
    Launch an interactive Claude brainstorming session in a new terminal window.

    Returns:
        session_id (str) — spec committed, session captured
        None             — user abandoned or error
    """
    project_dir = str(Path(item["project_dir"]).expanduser())
    if not Path(project_dir).exists():
        return None

    specs_dir = Path(project_dir) / "docs" / "superpowers" / "specs"
    specs_before = set(specs_dir.glob("*.md")) if specs_dir.exists() else set()

    claude_dir = Path(_claude_dir) if _claude_dir else Path.home() / ".claude" / "projects"
    sessions_before = set(claude_dir.glob("**/*.jsonl")) if claude_dir.exists() else set()

    script_path = None
    try:
        if sys.platform == "win32":
            script_path = _make_win_launch_script(item, claude_cmd)
            proc = subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", script_path],
                cwd=project_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            proc = subprocess.Popen([claude_cmd], cwd=project_dir)
    except (FileNotFoundError, PermissionError):
        if script_path:
            os.unlink(script_path)
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
    # If the loop never ran (process had already exited), treat all current specs
    # as candidates rather than diffing against specs_before.
    if new_spec is None and specs_dir.exists():
        specs_after = set(specs_dir.glob("*.md"))
        if loop_ran:
            candidates = specs_after - specs_before
        else:
            candidates = specs_after
        if candidates:
            new_spec = sorted(candidates, key=lambda p: p.stat().st_mtime)[-1]

    if new_spec is None:
        if script_path:
            try:
                os.unlink(script_path)
            except OSError:
                pass
        return None

    sessions_after = set(claude_dir.glob("**/*.jsonl")) if claude_dir.exists() else set()
    if loop_ran:
        new_sessions = sessions_after - sessions_before
    else:
        new_sessions = sessions_after
    if not new_sessions:
        if script_path:
            try:
                os.unlink(script_path)
            except OSError:
                pass
        return None

    if script_path:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    return Path(
        sorted(new_sessions, key=lambda p: p.stat().st_mtime)[-1]
    ).stem
