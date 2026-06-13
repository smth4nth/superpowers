# Brainstorm Loop — Design Spec

**Goal:** A persistent interactive loop (Loop 1) that picks todo items one at a time, opens an interactive Claude brainstorming session in a new terminal window, detects when the spec is written, auto-closes the session, and writes the resulting work item (with `session_id`) into the existing automation loop's queue (Loop 2).

---

## Context

The existing loop automation (`scripts/loop/controller.py`) runs fully autonomously. It launches `claude -p` sessions that run the full superpowers skill chain — brainstorming through finishing — without human involvement.

The problem: brainstorming is inherently interactive. Autonomous brainstorming produces specs that drift from user intent. Writing-plans based on a misunderstood spec causes the entire implementation to go wrong.

This spec introduces a two-loop architecture that keeps the human in the design phase and removes them from the implementation phase.

---

## Two-Loop Architecture

```
Loop 1 (brainstorm_controller.py)       Loop 2 (controller.py — existing)
  watches todo-items.json                 watches work-items.json
  picks pending todo item                 picks pending work item (has session_id)
  opens interactive Claude window         claude --resume <session_id> -p "..."
  user does brainstorming                          --dangerously-skip-permissions
  detects spec file written               writing-plans → subagent-driven-development
  auto-closes Claude window               → finishing-a-development-branch
  writes work item with session_id        writes state/<uuid>.json
  marks todo item done                    marks work item done/needs_human
```

The two loops communicate through `work-items.json`. Loop 1 writes, Loop 2's watchdog detects the change and picks up the new item automatically.

---

## File Layout

```
scripts/loop/
├── controller.py            ← existing Loop 2, unchanged
├── brainstorm_controller.py ← new Loop 1
├── brainstorm_session.py    ← new: interactive session + auto-close logic
├── todo_queue.py            ← new: reads/writes todo-items.json
├── session.py               ← modified: adds --resume support
└── work_queue.py            ← modified: adds add_item()

~/.config/superpowers/loop/
├── config.json              ← existing, unchanged
├── todo-items/
│   └── todo-items.json      ← new
├── work-items/
│   └── work-items.json      ← existing, gains session_id field
└── state/
    └── <uuid>.json          ← existing, unchanged
```

---

## Schemas

### `todo-items.json`

```json
{
  "items": [
    {
      "id": "1",
      "title": "Refactor auth module",
      "description": "Split auth.ts into session and token modules",
      "project_dir": "C:/Users/Baokun/projects/my-app",
      "status": "pending",
      "created_at": "2026-06-12T10:00:00Z",
      "updated_at": "2026-06-12T10:00:00Z"
    }
  ]
}
```

**Status values:** `pending` → `done`. No `needs_human` — if the user exits Claude before the spec is written, the item stays `pending` and will be retried fresh next time.

### `work-items.json` (schema addition)

One new field added to the existing schema:

```json
{
  "session_id": "4f7e8d9c-1a2b-3c4d-5e6f-7a8b9c0d1e2f"
}
```

`session_id` is `null` on manually-added work items. `session.py` uses `--resume` only when this field is present and non-null, preserving backward compatibility.

---

## Components

### `brainstorm_session.py`

Manages one interactive brainstorm session. Returns the `session_id` string on success, `None` if the user abandoned the session.

**Logic:**

1. Check `project_dir` exists — return `None` if not
2. Snapshot `docs/superpowers/specs/*.md` in the project
3. Snapshot `~/.claude/projects/**/*.jsonl`
4. Launch Claude in a new terminal window using `CREATE_NEW_CONSOLE` (Windows) to retain the process handle
5. Poll `specs_dir` every 2 seconds while `proc.poll() is None`
6. On new spec detected: sleep 3 seconds (allow git commit to complete), then `proc.terminate()`
7. Find the new `.jsonl` file — its stem is the `session_id`
8. Return `session_id`, or `None` if no new spec or no new session file found

**Platform handling:**

```python
if sys.platform == "win32":
    proc = subprocess.Popen(
        [claude_cmd],
        cwd=project_dir,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
else:
    proc = subprocess.Popen([claude_cmd], cwd=project_dir)
```

### `brainstorm_controller.py`

Mirrors `controller.py`. Watches `todo-items/` directory for changes to `todo-items.json`. On change (or at startup), calls `_drain_queue()`.

`_drain_queue()` loop:
- Call `todo_queue.next_pending()` — returns first `pending` item or `None`
- If `None`: log "Todo queue empty, watching..." and return
- Track seen item IDs to prevent infinite retry on the same item within one drain cycle
- Call `brainstorm_session.run(item)`
- If `session_id` returned: call `work_queue.add_item(item, session_id)` and `todo_queue.write_done(item)`
- If `None` returned: leave item as `pending` (user abandoned — fresh start next time)
- Continue loop

### `todo_queue.py`

Mirrors `work_queue.py`. Reads `~/.config/superpowers/loop/todo-items/todo-items.json`.

- `next_pending(path=None)` — returns first item where `status == "pending"`, or `None`
- `write_done(item, path=None)` — sets `status = "done"`, updates `updated_at`

### `work_queue.py` (addition)

New function:

```python
def add_item(todo_item, session_id, path=None):
    """Create a work item from a todo item and append to work-items.json."""
```

Copies `id`, `title`, `description`, `project_dir`, `created_at` from the todo item. Sets `session_id`, `status = "pending"`, `updated_at = now`, `blocker = null`, `human_input = null`, `state_id = null`.

### `session.py` (modification)

Adds `--resume` path when `item["session_id"]` is present:

```python
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
    cmd = [claude_cmd, "--resume", item["session_id"], "-p", prompt,
           "--dangerously-skip-permissions"]
else:
    # existing path unchanged
    ...
```

---

## End-to-End Data Flow

```
User adds item to todo-items.json
  → Loop 1 watchdog fires
  → brainstorm_controller._drain_queue()
  → brainstorm_session.run(item)
      → snapshot specs + sessions
      → Popen(claude, CREATE_NEW_CONSOLE)     ← new window opens
      → poll specs_dir every 2s
      → user brainstorms in new window
      → spec written + committed by Claude
      → new spec file detected
      → sleep(3) → proc.terminate()           ← window closes
      → find new .jsonl → extract session_id
      → return session_id
  → work_queue.add_item(item, session_id)     ← write to work-items.json
  → todo_queue.write_done(item)               ← todo item = done
  → work-items.json modified
      → Loop 2 watchdog fires
      → controller._drain_queue()
      → session.run(item)  [has session_id]
          → claude --resume <session_id> -p "[AUTONOMOUS MODE]..."
                   --dangerously-skip-permissions
          → (full brainstorm context in session)
          → writing-plans → subagent-driven-development
          → finishing-a-development-branch
              → writes state/<uuid>.json
              → work item status → done
```

---

## Error Handling

| Situation | Handling |
|-----------|----------|
| `project_dir` does not exist | `brainstorm_session.run` returns `None`; todo item stays `pending` |
| User closes window before spec written | `proc.poll()` returns; no new spec detected → return `None`; todo item stays `pending` |
| Spec detected but no new session file | Return `None`; todo item stays `pending` |
| `claude` binary not found | `Popen` raises `FileNotFoundError` → catch → return `None` |
| Same item fails repeatedly | `seen` set in `_drain_queue` prevents infinite retry within one drain cycle; item stays `pending` until `todo-items.json` changes again |
| Loop 2 resume fails (non-zero exit) | Existing `work_queue.write_needs_human` logic handles it unchanged |

---

## Starting the Loops

```bash
# Loop 1 (brainstorm, interactive)
python scripts/loop/brainstorm_controller.py

# Loop 2 (automation, existing)
python scripts/loop/controller.py
```

Both run as persistent foreground processes (e.g., two terminal windows or screen sessions).

---

## `config.json` (no changes required)

The existing `claude_cmd` field is reused by both loops. No new configuration fields are needed.
