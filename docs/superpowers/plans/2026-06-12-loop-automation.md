# Loop Automation Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent Python program that watches `work-items.json` and auto-launches `claude -p` sessions for each pending work item.

**Architecture:** Four focused modules — `work_queue.py` (read/write work-items.json), `session.py` (launch claude subprocess), `watcher.py` (watchdog event handler), `controller.py` (threading.Event dispatch loop). The controller sleeps on an Event; watchdog and startup both set it; one drain loop runs sessions sequentially.

**Tech Stack:** Python 3.10+, watchdog 6.x, pytest, stdlib only otherwise (subprocess, threading, json, pathlib, signal)

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `scripts/loop/work_queue.py` | Read work-items.json; find next pending; write needs_human |
| Create | `scripts/loop/session.py` | Build prompt; launch `claude -p` subprocess |
| Create | `scripts/loop/watcher.py` | watchdog handler; calls `controller.on_file_changed()` |
| Create | `scripts/loop/controller.py` | threading.Event loop; drain queue; startup check |
| Create | `scripts/loop/requirements.txt` | watchdog pin |
| Create | `tests/loop/test_work_queue.py` | Unit tests for work_queue |
| Create | `tests/loop/test_session.py` | Unit tests for session |
| Create | `tests/loop/test_controller.py` | Unit tests for controller._drain_queue |

---

## Task 1: `work_queue.py`

**Files:**
- Create: `scripts/loop/work_queue.py`
- Create: `tests/loop/test_work_queue.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/loop/test_work_queue.py`:

```python
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import work_queue as wq


def _write(tmp_path, items):
    f = tmp_path / "work-items.json"
    f.write_text(json.dumps({"items": items}), encoding="utf-8")
    return str(f)


def test_next_pending_returns_first_pending(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "done"},
        {"id": "2", "status": "pending", "title": "T", "description": "D"},
        {"id": "3", "status": "pending", "title": "T2", "description": "D2"},
    ])
    assert wq.next_pending(path)["id"] == "2"


def test_next_pending_skips_needs_human(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "needs_human"},
        {"id": "2", "status": "pending", "title": "T", "description": "D"},
    ])
    assert wq.next_pending(path)["id"] == "2"


def test_next_pending_returns_none_when_empty(tmp_path):
    path = _write(tmp_path, [])
    assert wq.next_pending(path) is None


def test_next_pending_returns_none_when_file_missing(tmp_path):
    assert wq.next_pending(str(tmp_path / "nope.json")) is None


def test_next_pending_returns_none_on_bad_json(tmp_path):
    f = tmp_path / "work-items.json"
    f.write_text("not json", encoding="utf-8")
    assert wq.next_pending(str(f)) is None


def test_write_needs_human_sets_status_and_blocker(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "pending", "title": "T", "description": "D",
         "blocker": None, "updated_at": "2026-06-12T00:00:00Z"},
    ])
    wq.write_needs_human({"id": "1"}, reason="exit code 1", path=path)
    data = json.loads(Path(path).read_text())
    wi = data["items"][0]
    assert wi["status"] == "needs_human"
    assert wi["blocker"]["context"] == "exit code 1"
    assert wi["updated_at"] != "2026-06-12T00:00:00Z"


def test_write_needs_human_noop_when_file_missing(tmp_path):
    wq.write_needs_human({"id": "1"}, "reason", path=str(tmp_path / "nope.json"))
    # must not raise
```

- [ ] **Step 2: Run tests — expect ImportError (module not yet created)**

```bash
cd C:/Users/Baokun/Desktop/Project/superpowers
python -m pytest tests/loop/test_work_queue.py -v
```

Expected: `ModuleNotFoundError: No module named 'work_queue'`

- [ ] **Step 3: Create `scripts/loop/work_queue.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT = (
    Path.home() / ".config" / "superpowers" / "loop"
    / "work-items" / "work-items.json"
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


def write_needs_human(item, reason, path=None):
    p = Path(path) if path else _DEFAULT
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for wi in data["items"]:
            if wi["id"] == item["id"]:
                wi["status"] = "needs_human"
                wi["blocker"] = {
                    "question": "Review the failure and retry or update the work item.",
                    "context": reason,
                }
                wi["updated_at"] = (
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                )
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, KeyError, OSError):
        pass
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
python -m pytest tests/loop/test_work_queue.py -v
```

Expected: 7 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/loop/work_queue.py tests/loop/test_work_queue.py
git commit -m "feat: add work_queue module for loop controller"
```

---

## Task 2: `session.py`

**Files:**
- Create: `scripts/loop/session.py`
- Create: `tests/loop/test_session.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/loop/test_session.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import session


def _item(tmp_path, **kwargs):
    base = {
        "id": "1",
        "title": "Fix auth bug",
        "description": "Refactor auth.ts into two modules",
        "project_dir": str(tmp_path),
    }
    base.update(kwargs)
    return base


def test_returns_minus_one_when_project_dir_missing(tmp_path):
    item = _item(tmp_path, project_dir=str(tmp_path / "nonexistent"))
    assert session.run(item) == -1


def test_returns_subprocess_exit_code(tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result):
        assert session.run(_item(tmp_path)) == 0


def test_prompt_contains_title_and_description(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    prompt = mock_run.call_args[0][0][2]
    assert "Fix auth bug" in prompt
    assert "Refactor auth.ts into two modules" in prompt


def test_prompt_contains_loop_metadata(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    prompt = mock_run.call_args[0][0][2]
    assert "loop_item_id: 1" in prompt
    assert "loop_started_at:" in prompt


def test_prompt_includes_human_input_when_present(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path, human_input="Use the new v2 API"))
    prompt = mock_run.call_args[0][0][2]
    assert "human_input: Use the new v2 API" in prompt


def test_prompt_omits_human_input_when_absent(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    prompt = mock_run.call_args[0][0][2]
    assert "human_input" not in prompt


def test_subprocess_cwd_is_project_dir(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    assert mock_run.call_args[1]["cwd"] == str(tmp_path)


def test_subprocess_uses_custom_claude_cmd(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path), claude_cmd="/usr/local/bin/claude")
    assert mock_run.call_args[0][0][0] == "/usr/local/bin/claude"
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/loop/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'session'`

- [ ] **Step 3: Create `scripts/loop/session.py`**

```python
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
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
python -m pytest tests/loop/test_session.py -v
```

Expected: 8 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/loop/session.py tests/loop/test_session.py
git commit -m "feat: add session module for loop controller"
```

---

## Task 3: `watcher.py`

**Files:**
- Create: `scripts/loop/watcher.py`
- Create: `scripts/loop/requirements.txt`

- [ ] **Step 1: Install watchdog**

```bash
pip install watchdog==6.0.0
```

Expected: Successfully installed watchdog-6.0.0

- [ ] **Step 2: Create `scripts/loop/requirements.txt`**

```
watchdog==6.0.0
```

- [ ] **Step 3: Create `scripts/loop/watcher.py`**

```python
from watchdog.events import FileSystemEventHandler


class WorkItemsHandler(FileSystemEventHandler):
    def __init__(self, filename, callback):
        self._filename = filename
        self._callback = callback

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(self._filename):
            self._callback()
```

- [ ] **Step 4: Smoke-test the import**

```bash
cd C:/Users/Baokun/Desktop/Project/superpowers/scripts/loop
python -c "from watcher import WorkItemsHandler; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/loop/watcher.py scripts/loop/requirements.txt
git commit -m "feat: add watcher module and requirements for loop controller"
```

---

## Task 4: `controller.py`

**Files:**
- Create: `scripts/loop/controller.py`
- Create: `tests/loop/test_controller.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/loop/test_controller.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub out watchdog before importing controller
sys.modules.setdefault("watchdog", MagicMock())
sys.modules.setdefault("watchdog.events", MagicMock())
sys.modules.setdefault("watchdog.observers", MagicMock())

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import controller as ctrl_mod
from controller import Controller


def _ctrl():
    return Controller(config={"claude_cmd": "claude"})


def test_drain_queue_processes_pending_item(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "session") as mock_s:
        mock_q.next_pending.side_effect = [item, None]
        mock_s.run.return_value = 0
        _ctrl()._drain_queue()
    mock_s.run.assert_called_once_with(item, claude_cmd="claude")


def test_drain_queue_writes_needs_human_on_nonzero_exit(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "session") as mock_s:
        mock_q.next_pending.side_effect = [item, None]
        mock_s.run.return_value = 2
        _ctrl()._drain_queue()
    mock_q.write_needs_human.assert_called_once_with(
        item, reason="claude exited with code 2"
    )


def test_drain_queue_writes_needs_human_on_missing_project_dir():
    item = {"id": "1", "title": "T", "description": "D", "project_dir": "/nope"}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "session") as mock_s:
        mock_q.next_pending.side_effect = [item, None]
        mock_s.run.return_value = -1
        _ctrl()._drain_queue()
    mock_q.write_needs_human.assert_called_once_with(
        item, reason="project_dir not found: /nope"
    )


def test_drain_queue_processes_multiple_items(tmp_path):
    item1 = {"id": "1", "title": "T1", "description": "D", "project_dir": str(tmp_path)}
    item2 = {"id": "2", "title": "T2", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "session") as mock_s:
        mock_q.next_pending.side_effect = [item1, item2, None]
        mock_s.run.return_value = 0
        _ctrl()._drain_queue()
    assert mock_s.run.call_count == 2


def test_on_file_changed_sets_wake_event():
    c = _ctrl()
    assert not c._wake.is_set()
    c.on_file_changed()
    assert c._wake.is_set()
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
python -m pytest tests/loop/test_controller.py -v
```

Expected: `ModuleNotFoundError: No module named 'controller'`

- [ ] **Step 3: Create `scripts/loop/controller.py`**

```python
import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path

import work_queue
import session
from watcher import WorkItemsHandler
from watchdog.observers import Observer

CONFIG_PATH = (
    Path.home() / ".config" / "superpowers" / "loop" / "config.json"
)
WORK_ITEMS_DIR = (
    Path.home() / ".config" / "superpowers" / "loop" / "work-items"
)
WORK_ITEMS_FILE = "work-items.json"

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
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


class Controller:
    def __init__(self, config):
        self._config = config
        self._wake = threading.Event()

    def on_file_changed(self):
        self._wake.set()

    def run(self):
        self._wake.set()  # process any pending items at startup
        while True:
            self._wake.wait()
            self._wake.clear()
            self._drain_queue()

    def _drain_queue(self):
        while True:
            item = work_queue.next_pending()
            if item is None:
                log.info("Queue empty, watching...")
                return
            log.info(f"Processing item {item['id']}: {item['title']}")
            exit_code = session.run(
                item, claude_cmd=self._config.get("claude_cmd", "claude")
            )
            if exit_code != 0:
                reason = (
                    f"project_dir not found: {item['project_dir']}"
                    if exit_code == -1
                    else f"claude exited with code {exit_code}"
                )
                log.warning(f"Item {item['id']} failed: {reason}")
                work_queue.write_needs_human(item, reason=reason)


def main():
    config = load_config()
    if not WORK_ITEMS_DIR.exists():
        log.error(f"work-items directory not found: {WORK_ITEMS_DIR}")
        sys.exit(1)

    controller = Controller(config)
    handler = WorkItemsHandler(WORK_ITEMS_FILE, controller.on_file_changed)
    observer = Observer()
    observer.schedule(handler, str(WORK_ITEMS_DIR), recursive=False)
    observer.start()
    log.info("Loop controller started. Watching work-items.json...")

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

- [ ] **Step 4: Run all tests — expect all pass**

```bash
python -m pytest tests/loop/ -v
```

Expected: 20 tests PASSED (7 work_queue + 8 session + 5 controller)

- [ ] **Step 5: Commit**

```bash
git add scripts/loop/controller.py tests/loop/test_controller.py
git commit -m "feat: add controller module — loop automation complete"
```

---

## Task 5: Config Setup & Smoke Test

**Files:**
- No code changes — runtime config and manual verification

- [ ] **Step 1: Create config and work-items files**

```powershell
$base = "$env:USERPROFILE\.config\superpowers\loop"
New-Item -ItemType Directory -Force "$base\work-items"
New-Item -ItemType Directory -Force "$base\state"

# config.json
'{"claude_cmd": "claude"}' | Out-File -Encoding utf8 "$base\config.json"

# work-items.json with one test item (use a real project path)
@'
{
  "items": [
    {
      "id": "smoke-1",
      "title": "Smoke test item",
      "description": "This is a smoke test. Say hello and stop.",
      "project_dir": "C:/Users/Baokun/Desktop/Project/superpowers",
      "status": "pending",
      "created_at": "2026-06-12T00:00:00Z",
      "updated_at": "2026-06-12T00:00:00Z",
      "blocker": null,
      "human_input": null,
      "state_id": null
    }
  ]
}
'@ | Out-File -Encoding utf8 "$base\work-items\work-items.json"
```

- [ ] **Step 2: Start the controller**

```bash
cd C:/Users/Baokun/Desktop/Project/superpowers/scripts/loop
python controller.py
```

Expected output:
```
2026-06-12T... INFO Loop controller started. Watching work-items.json...
2026-06-12T... INFO Processing item smoke-1: Smoke test item
```

- [ ] **Step 3: Verify the item was processed**

After the claude session completes, check:

```powershell
Get-Content "$env:USERPROFILE\.config\superpowers\loop\work-items\work-items.json"
```

Expected: `"status": "done"` and `"state_id": "<some-uuid>"`

- [ ] **Step 4: Stop and final commit**

`Ctrl+C` to stop the controller.

```bash
git add scripts/loop/
git commit -m "chore: finalize loop automation controller"
```
