# Brainstorm Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent interactive Loop 1 that picks todo items, runs a brainstorming session in a new terminal window, auto-closes when the spec is committed, and writes the resulting work item (with `session_id`) into Loop 2's queue.

**Architecture:** Mirror the existing `controller.py` / `session.py` / `work_queue.py` pattern. New modules (`todo_queue`, `brainstorm_session`, `brainstorm_controller`) follow identical structure. `session.py` and `work_queue.py` get minimal additions. No existing behaviour changes.

**Tech Stack:** Python 3, watchdog (already in requirements.txt), subprocess, threading, pathlib.

---

### Task 1: `todo_queue.py`

Mirrors `work_queue.py`. Reads/writes `~/.config/superpowers/loop/todo-items/todo-items.json`.

**Files:**
- Create: `scripts/loop/todo_queue.py`
- Create: `tests/loop/test_todo_queue.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/loop/test_todo_queue.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import todo_queue as tq


def _write(tmp_path, items):
    f = tmp_path / "todo-items.json"
    f.write_text(json.dumps({"items": items}), encoding="utf-8")
    return str(f)


def test_next_pending_returns_first_pending(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "done"},
        {"id": "2", "status": "pending", "title": "T"},
        {"id": "3", "status": "pending", "title": "T2"},
    ])
    assert tq.next_pending(path)["id"] == "2"


def test_next_pending_returns_none_when_all_done(tmp_path):
    path = _write(tmp_path, [{"id": "1", "status": "done"}])
    assert tq.next_pending(path) is None


def test_next_pending_returns_none_when_empty(tmp_path):
    path = _write(tmp_path, [])
    assert tq.next_pending(path) is None


def test_next_pending_returns_none_when_file_missing(tmp_path):
    assert tq.next_pending(str(tmp_path / "nope.json")) is None


def test_next_pending_returns_none_on_bad_json(tmp_path):
    f = tmp_path / "todo-items.json"
    f.write_text("not json", encoding="utf-8")
    assert tq.next_pending(str(f)) is None


def test_write_done_sets_status_and_updates_timestamp(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "pending", "title": "T",
         "updated_at": "2026-06-12T00:00:00Z"},
    ])
    tq.write_done({"id": "1"}, path=path)
    data = json.loads(Path(path).read_text())
    assert data["items"][0]["status"] == "done"
    assert data["items"][0]["updated_at"] != "2026-06-12T00:00:00Z"


def test_write_done_noop_when_file_missing(tmp_path):
    tq.write_done({"id": "1"}, path=str(tmp_path / "nope.json"))
    # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\Baokun\Desktop\Project\superpowers
pytest tests/loop/test_todo_queue.py -v
```

Expected: `ModuleNotFoundError: No module named 'todo_queue'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/loop/todo_queue.py
import json
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT = (
    Path.home() / ".config" / "superpowers" / "loop"
    / "todo-items" / "todo-items.json"
)


def next_pending(path=None):
    p = Path(path) if path else _DEFAULT
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            if item.get("status") == "pending":
                return item
    except (json.JSONDecodeError, OSError):
        return None
    return None


def write_done(item, path=None):
    p = Path(path) if path else _DEFAULT
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for ti in data["items"]:
            if ti["id"] == item["id"]:
                ti["status"] = "done"
                ti["updated_at"] = (
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                )
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, KeyError, OSError):
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/loop/test_todo_queue.py -v
```

Expected: `7 passed`

- [ ] **Step 5: Commit**

```
git add scripts/loop/todo_queue.py tests/loop/test_todo_queue.py
git commit -m "feat: add todo_queue module for brainstorm loop"
```

---

### Task 2: `work_queue.add_item()`

Adds a single function to the existing `work_queue.py`. Creates a work item from a todo item + session_id and appends it to `work-items.json`, creating the file if it doesn't exist.

**Files:**
- Modify: `scripts/loop/work_queue.py`
- Modify: `tests/loop/test_work_queue.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to the end of `tests/loop/test_work_queue.py`:

```python
def test_add_item_appends_work_item(tmp_path):
    path = _write(tmp_path, [])
    todo_item = {
        "id": "1",
        "title": "Fix auth",
        "description": "Refactor auth.ts",
        "project_dir": str(tmp_path),
        "created_at": "2026-06-12T10:00:00Z",
    }
    wq.add_item(todo_item, session_id="abc-123", path=path)
    data = json.loads(Path(path).read_text())
    assert len(data["items"]) == 1
    wi = data["items"][0]
    assert wi["id"] == "1"
    assert wi["title"] == "Fix auth"
    assert wi["session_id"] == "abc-123"
    assert wi["status"] == "pending"
    assert wi["blocker"] is None
    assert wi["state_id"] is None
    assert wi["human_input"] is None


def test_add_item_creates_file_when_missing(tmp_path):
    path = str(tmp_path / "work-items.json")
    todo_item = {
        "id": "2", "title": "T", "description": "D",
        "project_dir": str(tmp_path), "created_at": "2026-06-12T10:00:00Z",
    }
    wq.add_item(todo_item, session_id="xyz-456", path=path)
    data = json.loads(Path(path).read_text())
    assert data["items"][0]["session_id"] == "xyz-456"


def test_add_item_preserves_existing_items(tmp_path):
    path = _write(tmp_path, [
        {"id": "existing", "status": "done", "title": "old"},
    ])
    todo_item = {
        "id": "new", "title": "New", "description": "D",
        "project_dir": str(tmp_path), "created_at": "2026-06-12T10:00:00Z",
    }
    wq.add_item(todo_item, session_id="s1", path=path)
    data = json.loads(Path(path).read_text())
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "existing"
    assert data["items"][1]["id"] == "new"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/loop/test_work_queue.py::test_add_item_appends_work_item tests/loop/test_work_queue.py::test_add_item_creates_file_when_missing tests/loop/test_work_queue.py::test_add_item_preserves_existing_items -v
```

Expected: `AttributeError: module 'work_queue' has no attribute 'add_item'`

- [ ] **Step 3: Add `add_item` to `scripts/loop/work_queue.py`**

Append after the existing `write_needs_human` function:

```python
def add_item(todo_item, session_id, path=None):
    p = Path(path) if path else _DEFAULT
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"items": []}, indent=2), encoding="utf-8")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        data["items"].append({
            "id": todo_item["id"],
            "title": todo_item["title"],
            "description": todo_item["description"],
            "project_dir": todo_item["project_dir"],
            "status": "pending",
            "session_id": session_id,
            "created_at": todo_item.get("created_at", now),
            "updated_at": now,
            "blocker": None,
            "human_input": None,
            "state_id": None,
        })
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, KeyError, OSError):
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/loop/test_work_queue.py -v
```

Expected: all tests pass (existing + 3 new)

- [ ] **Step 5: Commit**

```
git add scripts/loop/work_queue.py tests/loop/test_work_queue.py
git commit -m "feat: add work_queue.add_item for brainstorm loop handoff"
```

---

### Task 3: `session.py` — `--resume` support

When `item["session_id"]` is present, use `--resume <session_id> -p "<prompt>"`. Otherwise fall through to the existing path unchanged.

**Files:**
- Modify: `scripts/loop/session.py`
- Modify: `tests/loop/test_session.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to the end of `tests/loop/test_session.py`:

```python
def test_uses_resume_flag_when_session_id_present(tmp_path):
    mock_result = MagicMock(returncode=0)
    item = _item(tmp_path, session_id="abc-123-def")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(item)
    cmd = mock_run.call_args[0][0]
    assert "--resume" in cmd
    assert "abc-123-def" in cmd


def test_skips_resume_when_no_session_id(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    cmd = mock_run.call_args[0][0]
    assert "--resume" not in cmd


def test_resume_prompt_contains_required_fields(tmp_path):
    mock_result = MagicMock(returncode=0)
    item = _item(tmp_path, session_id="abc-123")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(item)
    # cmd: [claude, "--resume", session_id, "-p", prompt, "--dangerously-skip-permissions"]
    prompt = mock_run.call_args[0][0][4]
    assert "AUTONOMOUS MODE" in prompt
    assert "writing-plans" in prompt
    assert "loop_item_id: 1" in prompt
    assert "loop_started_at:" in prompt


def test_resume_prompt_omits_title_and_description(tmp_path):
    mock_result = MagicMock(returncode=0)
    item = _item(tmp_path, session_id="abc-123")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(item)
    prompt = mock_run.call_args[0][0][4]
    assert "Fix auth bug" not in prompt
    assert "Refactor auth.ts" not in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/loop/test_session.py::test_uses_resume_flag_when_session_id_present tests/loop/test_session.py::test_skips_resume_when_no_session_id tests/loop/test_session.py::test_resume_prompt_contains_required_fields tests/loop/test_session.py::test_resume_prompt_omits_title_and_description -v
```

Expected: `AssertionError` (no `--resume` in cmd)

- [ ] **Step 3: Rewrite `scripts/loop/session.py`**

Full file replacement (existing logic preserved in the `else` branch):

```python
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
    if not Path(item["project_dir"]).exists():
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
```

- [ ] **Step 4: Run all session tests to verify they pass**

```
pytest tests/loop/test_session.py -v
```

Expected: all tests pass (existing + 4 new)

- [ ] **Step 5: Commit**

```
git add scripts/loop/session.py tests/loop/test_session.py
git commit -m "feat: add --resume support to session.py for brainstorm loop handoff"
```

---

### Task 4: `brainstorm_session.py`

Launches Claude in a new terminal window (retaining the process handle), polls for a new spec file in `docs/superpowers/specs/`, waits for it to be git-committed, then terminates the process and returns the session_id.

**Files:**
- Create: `scripts/loop/brainstorm_session.py`
- Create: `tests/loop/test_brainstorm_session.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/loop/test_brainstorm_session.py
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import brainstorm_session as bs


def _item(project_dir):
    return {"id": "1", "title": "T", "project_dir": str(project_dir)}


def test_returns_none_when_project_dir_missing(tmp_path):
    item = {"id": "1", "title": "T", "project_dir": str(tmp_path / "nope")}
    assert bs.run(item) is None


def test_returns_none_when_no_spec_written(tmp_path):
    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, None, 0]
    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"):
        result = bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))
    assert result is None


def test_returns_none_when_spec_written_but_no_session_file(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()

    mock_proc = MagicMock()
    call_count = [0]

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-12-spec-design.md").write_text("spec")
        return None if call_count[0] < 3 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"), \
         patch.object(bs, "_spec_committed", return_value=True):
        result = bs.run(_item(tmp_path), _claude_dir=str(claude_dir))
    assert result is None


def test_returns_session_id_when_spec_and_session_found(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "my-project"
    claude_dir.mkdir(parents=True)

    mock_proc = MagicMock()
    call_count = [0]

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-12-spec-design.md").write_text("spec")
            (claude_dir / "my-session-id.jsonl").write_text("{}")
        return None if call_count[0] < 3 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"), \
         patch.object(bs, "_spec_committed", return_value=True):
        result = bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))
    assert result == "my-session-id"


def test_terminates_process_when_spec_detected(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "proj"
    claude_dir.mkdir(parents=True)

    mock_proc = MagicMock()
    call_count = [0]

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-12-spec-design.md").write_text("spec")
            (claude_dir / "sess.jsonl").write_text("{}")
        return None if call_count[0] < 4 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"), \
         patch.object(bs, "_spec_committed", return_value=True):
        bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))

    mock_proc.terminate.assert_called_once()


def test_returns_session_id_when_user_exits_naturally_with_spec(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "proj"
    claude_dir.mkdir(parents=True)
    (specs_dir / "2026-06-12-spec-design.md").write_text("spec")
    (claude_dir / "natural-exit-session.jsonl").write_text("{}")

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0  # already exited

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"):
        result = bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))
    assert result == "natural-exit-session"


def test_spec_committed_returns_true_on_clean_status(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert bs._spec_committed(str(tmp_path), tmp_path / "spec.md") is True


def test_spec_committed_returns_false_on_dirty_status(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="?? spec.md\n")
        assert bs._spec_committed(str(tmp_path), tmp_path / "spec.md") is False


def test_spec_committed_returns_false_on_os_error(tmp_path):
    with patch("subprocess.run", side_effect=OSError("no git")):
        assert bs._spec_committed(str(tmp_path), tmp_path / "spec.md") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/loop/test_brainstorm_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'brainstorm_session'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/loop/brainstorm_session.py
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
    Launch an interactive Claude brainstorming session in a new terminal window.

    Returns:
        session_id (str) — spec committed, session captured
        None             — user abandoned or error
    """
    project_dir = item["project_dir"]
    if not Path(project_dir).exists():
        return None

    specs_dir = Path(project_dir) / "docs" / "superpowers" / "specs"
    specs_before = set(specs_dir.glob("*.md")) if specs_dir.exists() else set()

    claude_dir = Path(_claude_dir) if _claude_dir else Path.home() / ".claude" / "projects"
    sessions_before = set(claude_dir.glob("**/*.jsonl"))

    try:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                [claude_cmd],
                cwd=project_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            proc = subprocess.Popen([claude_cmd], cwd=project_dir)
    except (FileNotFoundError, PermissionError):
        return None

    new_spec = None

    while proc.poll() is None:
        time.sleep(2)
        if specs_dir.exists():
            specs_after = set(specs_dir.glob("*.md"))
            new_specs = specs_after - specs_before
            if new_specs:
                new_spec = sorted(new_specs, key=lambda p: p.stat().st_mtime)[-1]
                _wait_for_commit(project_dir, new_spec)
                proc.terminate()
                break

    # Final check: user may have exited naturally after writing the spec
    if new_spec is None and specs_dir.exists():
        specs_after = set(specs_dir.glob("*.md"))
        new_specs = specs_after - specs_before
        if new_specs:
            new_spec = sorted(new_specs, key=lambda p: p.stat().st_mtime)[-1]

    if new_spec is None:
        return None

    sessions_after = set(claude_dir.glob("**/*.jsonl"))
    new_sessions = sessions_after - sessions_before
    if not new_sessions:
        return None

    return Path(
        sorted(new_sessions, key=lambda p: p.stat().st_mtime)[-1]
    ).stem
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/loop/test_brainstorm_session.py -v
```

Expected: `9 passed`

- [ ] **Step 5: Commit**

```
git add scripts/loop/brainstorm_session.py tests/loop/test_brainstorm_session.py
git commit -m "feat: add brainstorm_session module — interactive session with auto-close"
```

---

### Task 5: `brainstorm_controller.py`

Mirrors `controller.py`. Watches `todo-items.json`, calls `brainstorm_session.run` for each pending item, and hands off to `work_queue.add_item` on success.

**Files:**
- Create: `scripts/loop/brainstorm_controller.py`
- Create: `tests/loop/test_brainstorm_controller.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/loop/test_brainstorm_controller.py
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("watchdog", MagicMock())
sys.modules.setdefault("watchdog.events", MagicMock())
sys.modules.setdefault("watchdog.observers", MagicMock())

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import brainstorm_controller as bc_mod
from brainstorm_controller import BrainstormController


def _ctrl():
    return BrainstormController(config={"claude_cmd": "claude"})


def test_drain_queue_calls_brainstorm_session(tmp_path):
    item = {"id": "1", "title": "T", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs, \
         patch.object(bc_mod, "work_queue") as mock_wq:
        mock_tq.next_pending.side_effect = [item, None]
        mock_bs.run.return_value = "session-abc"
        _ctrl()._drain_queue()
    mock_bs.run.assert_called_once_with(item, claude_cmd="claude")


def test_drain_queue_writes_work_item_on_success(tmp_path):
    item = {"id": "1", "title": "T", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs, \
         patch.object(bc_mod, "work_queue") as mock_wq:
        mock_tq.next_pending.side_effect = [item, None]
        mock_bs.run.return_value = "session-abc"
        _ctrl()._drain_queue()
    mock_wq.add_item.assert_called_once_with(item, session_id="session-abc")
    mock_tq.write_done.assert_called_once_with(item)


def test_drain_queue_skips_work_item_on_abandoned(tmp_path):
    item = {"id": "1", "title": "T", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs, \
         patch.object(bc_mod, "work_queue") as mock_wq:
        mock_tq.next_pending.side_effect = [item, None]
        mock_bs.run.return_value = None
        _ctrl()._drain_queue()
    mock_wq.add_item.assert_not_called()
    mock_tq.write_done.assert_not_called()


def test_drain_queue_processes_multiple_items(tmp_path):
    item1 = {"id": "1", "title": "T1", "project_dir": str(tmp_path)}
    item2 = {"id": "2", "title": "T2", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs, \
         patch.object(bc_mod, "work_queue"):
        mock_tq.next_pending.side_effect = [item1, item2, None]
        mock_bs.run.return_value = "session-xyz"
        _ctrl()._drain_queue()
    assert mock_bs.run.call_count == 2


def test_drain_queue_breaks_on_repeated_item(tmp_path):
    item = {"id": "1", "title": "T", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs, \
         patch.object(bc_mod, "work_queue"):
        mock_tq.next_pending.return_value = item
        mock_bs.run.return_value = None  # always abandoned, item stays pending
        _ctrl()._drain_queue()
    assert mock_bs.run.call_count == 1


def test_on_file_changed_sets_wake_event():
    c = _ctrl()
    assert not c._wake.is_set()
    c.on_file_changed()
    assert c._wake.is_set()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/loop/test_brainstorm_controller.py -v
```

Expected: `ModuleNotFoundError: No module named 'brainstorm_controller'`

- [ ] **Step 3: Write the implementation**

```python
# scripts/loop/brainstorm_controller.py
import json
import logging
import signal
import sys
import threading
from pathlib import Path

import todo_queue
import work_queue
import brainstorm_session
from watcher import WorkItemsHandler
from watchdog.observers import Observer

CONFIG_PATH = (
    Path.home() / ".config" / "superpowers" / "loop" / "config.json"
)
TODO_ITEMS_DIR = (
    Path.home() / ".config" / "superpowers" / "loop" / "todo-items"
)
TODO_ITEMS_FILE = "todo-items.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config():
    if not CONFIG_PATH.exists():
        log.error(
            f"Config not found at {CONFIG_PATH}. "
            'Create it with: {"claude_cmd": "claude"}'
        )
        sys.exit(1)
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        log.error(f"Config at {CONFIG_PATH} is not valid JSON: {e}")
        sys.exit(1)


class BrainstormController:
    def __init__(self, config):
        self._config = config
        self._wake = threading.Event()

    def on_file_changed(self):
        self._wake.set()

    def run(self):
        self._wake.set()
        while True:
            self._wake.wait()
            self._wake.clear()
            self._drain_queue()

    def _drain_queue(self):
        seen = set()
        while True:
            item = todo_queue.next_pending()
            if item is None:
                log.info("Todo queue empty, watching...")
                return
            if item["id"] in seen:
                log.warning(
                    f"Item {item['id']} still pending after session — "
                    "skipping until next file change"
                )
                return
            seen.add(item["id"])
            log.info(f"Starting brainstorm for item {item['id']}: {item['title']}")
            session_id = brainstorm_session.run(
                item, claude_cmd=self._config.get("claude_cmd", "claude")
            )
            if session_id:
                log.info(
                    f"Brainstorm complete for item {item['id']}, "
                    f"session_id={session_id}"
                )
                work_queue.add_item(item, session_id=session_id)
                todo_queue.write_done(item)
            else:
                log.info(
                    f"Brainstorm abandoned for item {item['id']}, keeping pending"
                )


def main():
    config = load_config()
    if not TODO_ITEMS_DIR.exists():
        log.error(f"todo-items directory not found: {TODO_ITEMS_DIR}")
        sys.exit(1)

    controller = BrainstormController(config)
    handler = WorkItemsHandler(TODO_ITEMS_FILE, controller.on_file_changed)
    observer = Observer()
    observer.schedule(handler, str(TODO_ITEMS_DIR), recursive=False)
    observer.start()
    log.info("Brainstorm controller started. Watching todo-items.json...")

    def shutdown(sig, frame):
        log.info("Shutting down...")
        observer.stop()
        observer.join()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    controller.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all loop tests to verify everything passes**

```
pytest tests/loop/ -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```
git add scripts/loop/brainstorm_controller.py tests/loop/test_brainstorm_controller.py
git commit -m "feat: add brainstorm_controller — Loop 1 complete"
```
