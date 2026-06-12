# Loop Automation Controller — Design Spec

**Goal:** A persistent Python program that watches `work-items.json` for changes and automatically launches a `claude -p` session for each pending work item, enabling fully autonomous loop execution across multiple repos.

---

## Context

This is the Automations layer of the Loop Engineering workflow built on superpowers. The other five components are already in place (Skills, Worktrees, Sub-agents, Plugins/Connectors, State). This controller is the missing piece that drives the loop without human intervention.

---

## File Layout

Placed in the superpowers repo under `scripts/loop/`, alongside existing scripts:

```
scripts/loop/
├── controller.py      ← main entry point, owns state machine and scheduling
├── watcher.py         ← watchdog FileSystemEventHandler
├── session.py         ← builds prompt, launches claude subprocess
├── queue.py           ← reads work-items.json, finds next pending item
└── requirements.txt   ← watchdog==6.x
```

Runtime files live outside the project directory (same root as work-items and state):

```
~/.config/superpowers/loop/
├── config.json              ← controller configuration
├── work-items/
│   └── work-items.json      ← human-managed task queue
└── state/
    └── <uuid>.json          ← per-session run records
```

---

## Configuration

`~/.config/superpowers/loop/config.json`:

```json
{
  "claude_cmd": "claude"
}
```

`claude_cmd` defaults to `"claude"` (assumes it is on PATH). No global `project_dir` — each work item carries its own.

---

## Work Item Schema (updated)

```json
{
  "id": "1",
  "title": "Refactor auth module",
  "description": "Split auth.ts into session and token modules",
  "project_dir": "C:/Users/Baokun/projects/my-app",
  "status": "pending",
  "created_at": "2026-06-12T10:00:00Z",
  "updated_at": "2026-06-12T10:00:00Z",
  "blocker": null,
  "human_input": null,
  "state_id": null
}
```

`project_dir` is required on every item. The controller uses it as the subprocess `cwd`.

---

## Components

### `queue.py`

Reads `~/.config/superpowers/loop/work-items/work-items.json` and returns the first item where `status == "pending"`. Items with `needs_human` are skipped. Returns `None` if the queue is empty.

Also exposes `write_needs_human(item, reason)` — called by `controller.py` when a subprocess exits non-zero (i.e. the skill chain crashed before `finishing-a-development-branch` could write state). Writes `status = "needs_human"` and `blocker = {question, context}` directly to `work-items.json`.

### `watcher.py`

Subclass of `watchdog.events.FileSystemEventHandler`. Watches the directory containing `work-items.json`. On `on_modified`, calls `controller.on_file_changed()`.

### `session.py`

Builds the prompt and launches the claude subprocess:

```python
prompt = f"""{item['title']}

{item['description']}
{f"\\nhuman_input: {item['human_input']}" if item.get('human_input') else ""}

loop_item_id: {item['id']}
loop_started_at: {started_at}"""

subprocess.run(
    [config["claude_cmd"], "-p", prompt, "--dangerously-skip-permissions"],
    cwd=item["project_dir"],
)
```

The `loop_item_id` and `loop_started_at` fields in the prompt are consumed by the `finishing-a-development-branch` skill (Step 7) to write the run record and update `work-items.json`.

Superpowers skills trigger automatically via the session-start hook — no explicit skill invocation in the prompt.

If `project_dir` does not exist on disk, `session.py` writes `needs_human` directly to the work item (with a descriptive blocker message) and returns without launching a subprocess.

### `controller.py`

Owns the single `is_running` flag and the main dispatch loop:

```
startup:
  load config
  check queue immediately (process any pending items found at start)
  start watchdog observer on work-items directory

on_file_changed():
  if is_running: return  (session will re-check on exit)
  dispatch()

dispatch():
  while True:
    item = queue.next_pending()
    if item is None:
      log "queue empty, watching..."
      return
    is_running = True
    exit_code = session.run(item)
    if exit_code != 0:
      queue.write_needs_human(item, reason=f"claude exited with code {exit_code}")
    is_running = False
```

---

## Data Flow

```
Human edits work-items.json (adds item or resolves needs_human)
  → watchdog fires on_modified
  → controller.on_file_changed()
  → is_running? skip : dispatch()
  → queue.next_pending() → item
  → session.run(item)
      → subprocess: claude -p "<title>\n<desc>\nloop_item_id: ...\nloop_started_at: ..."
         cwd = item.project_dir
      → superpowers session-start hook fires → skills auto-trigger
      → skill chain: brainstorming → writing-plans → subagent-driven-development
                     → finishing-a-development-branch (writes state + updates work-items.json)
      → subprocess exits
  → dispatch() again
  → no more pending → "queue empty, watching..."
```

---

## Error Handling

| Situation | Handling |
|-----------|----------|
| `claude` subprocess exits non-zero | Log error; write `needs_human` on the item with exit reason as blocker; continue to next item |
| `work-items.json` missing or malformed JSON | Log error; keep watching; retry when file is next modified |
| File changes while session is running | Ignore; `dispatch()` re-checks immediately after session exits |
| Pending items exist at startup | Process immediately without waiting for a file change |
| `project_dir` does not exist | Write `needs_human` directly; skip subprocess launch |
| Ctrl+C / SIGINT | Wait for current subprocess to finish, then exit cleanly |
| `needs_human` items | `queue.py` skips them; never passed to `session.run()` |

---

## Starting the Controller

```bash
pip install -r scripts/loop/requirements.txt
python scripts/loop/controller.py
```

The program runs until interrupted. It is expected to run persistently (e.g. in a terminal, a screen session, or as a Windows background task).
