# Loop Agent Selection Design

**Goal:** Let loop automation run either Claude or Codex per todo/work item, while preserving the current Claude behavior as the default.

## Current State

Loop automation has two queues:

- `todo-items/todo-items.json` feeds the interactive brainstorm loop.
- `work-items/work-items.json` feeds the autonomous implementation loop.

The current implementation assumes Claude everywhere. `brainstorm_session.py` seeds and resumes Claude sessions, discovers Claude session IDs from `~/.claude/projects/**/*.jsonl`, and opens `claude --resume` in a new terminal. `session.py` launches `claude -p` or `claude --resume ... -p`.

## Desired Behavior

Each todo or work item may declare which agent should run it:

```json
{
  "agent": "claude"
}
```

or:

```json
{
  "agent": "codex"
}
```

If an item omits `agent`, the loop uses `config.default_agent`, falling back to `claude` when the config also omits it. When Loop 1 creates a work item from a todo item, it copies the selected agent onto the work item so Loop 2 resumes with the same harness.

## Configuration

`~/.config/superpowers/loop/config.json` supports both the existing shape and a new multi-agent shape:

```json
{
  "default_agent": "claude",
  "agents": {
    "claude": {
      "cmd": "claude"
    },
    "codex": {
      "cmd": "codex"
    }
  }
}
```

For backward compatibility, `{ "claude_cmd": "claude" }` still works and maps to the Claude runner.

## Architecture

Add an `agent_runner.py` module that owns harness selection. Controllers call:

```python
agent_runner.run_work_item(item, config)
agent_runner.run_brainstorm_item(item, config)
```

The existing `session.py` and `brainstorm_session.py` stay Claude-specific for now. New Codex-specific behavior lives in focused modules, not in the controllers.

## Claude Runner

Claude keeps the current behavior:

- Work item without `session_id`: `claude -p <prompt> --dangerously-skip-permissions`
- Work item with `session_id`: `claude --resume <session_id> -p <prompt> --dangerously-skip-permissions`
- Brainstorm item: seed with `claude -p`, find the new `~/.claude/projects/**/*.jsonl`, then open `claude --resume <session_id>` interactively.

## Codex Runner

Codex uses the CLI's native non-interactive and resume commands:

- Work item without `session_id`: `codex exec <prompt> -C <project_dir> --dangerously-bypass-approvals-and-sandbox --dangerously-bypass-hook-trust`
- Work item with `session_id`: `codex exec resume <session_id> <prompt> -C <project_dir> --dangerously-bypass-approvals-and-sandbox --dangerously-bypass-hook-trust`
- Brainstorm item: launch `codex <prompt> -C <project_dir>` in an interactive terminal, detect a committed spec file, and return the latest new Codex session ID.

Codex session discovery is file-system based like Claude's. The search root is configurable for tests and defaults to `~/.codex/sessions`.

## Error Handling

Unknown agent names are treated as launch failures and mark work items `needs_human` with a clear reason. Missing binaries continue to return the existing `-2` runner error. Missing project directories continue to return `-1`.

Todo items remain `pending` when brainstorm launch fails or the user exits without writing a spec, matching current behavior.

## Testing

Tests cover:

- Agent selection from item, default config, and legacy `claude_cmd`.
- Work controller passes config to the runner instead of a Claude command.
- Brainstorm controller copies the todo item's agent into the generated work item.
- Codex work command construction for fresh and resumed work items.
- Codex brainstorm command construction and session ID discovery.
- Unknown agents fail without invoking subprocesses.
