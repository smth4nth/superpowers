# Loop Agent Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add item-level Claude/Codex selection to loop automation.

**Architecture:** Introduce `agent_runner.py` as the selection boundary. Keep Claude code in existing `session.py` and `brainstorm_session.py`; add Codex-specific command builders in `codex_session.py` and `codex_brainstorm_session.py`. Controllers delegate to the runner and stay queue-focused.

**Tech Stack:** Python 3, pytest, subprocess, pathlib, existing watchdog loop modules.

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `scripts/loop/agent_runner.py` | Resolve item agent and dispatch to Claude or Codex modules |
| Create | `scripts/loop/codex_session.py` | Run Codex autonomous work items |
| Create | `scripts/loop/codex_brainstorm_session.py` | Run Codex interactive brainstorm items |
| Modify | `scripts/loop/controller.py` | Delegate work items through `agent_runner` |
| Modify | `scripts/loop/brainstorm_controller.py` | Delegate brainstorm items through `agent_runner` |
| Modify | `scripts/loop/work_queue.py` | Copy `agent` from todo item into work item |
| Test | `tests/loop/test_agent_runner.py` | Selection and config compatibility tests |
| Test | `tests/loop/test_codex_session.py` | Codex command behavior |
| Test | `tests/loop/test_codex_brainstorm_session.py` | Codex brainstorm behavior |
| Modify | `tests/loop/test_controller.py` | Controller delegation tests |
| Modify | `tests/loop/test_brainstorm_controller.py` | Brainstorm delegation and work item tests |
| Modify | `tests/loop/test_work_queue.py` | Agent field propagation test |

---

## Tasks

### Task 1: Agent Field Propagation

- [ ] Add a failing test in `tests/loop/test_work_queue.py` proving `work_queue.add_item()` copies `todo_item["agent"]` into the generated work item.
- [ ] Run `python -m pytest tests/loop/test_work_queue.py -v` and verify the new test fails.
- [ ] Update `scripts/loop/work_queue.py` to include `"agent": todo_item.get("agent")` only when the todo item declares it.
- [ ] Re-run `python -m pytest tests/loop/test_work_queue.py -v` and verify it passes.

### Task 2: Codex Work Runner

- [ ] Add failing tests in `tests/loop/test_codex_session.py` for missing project dir, fresh command, resume command, custom `codex_cmd`, and missing binary.
- [ ] Run `python -m pytest tests/loop/test_codex_session.py -v` and verify import failure.
- [ ] Create `scripts/loop/codex_session.py` with `run(item, codex_cmd="codex")`.
- [ ] Re-run `python -m pytest tests/loop/test_codex_session.py -v` and verify it passes.

### Task 3: Codex Brainstorm Runner

- [ ] Add failing tests in `tests/loop/test_codex_brainstorm_session.py` for missing project dir, no session created, no spec written, spec committed, process termination, and custom session dir.
- [ ] Run `python -m pytest tests/loop/test_codex_brainstorm_session.py -v` and verify import failure.
- [ ] Create `scripts/loop/codex_brainstorm_session.py` with `run(item, codex_cmd="codex", _codex_dir=None)`.
- [ ] Re-run `python -m pytest tests/loop/test_codex_brainstorm_session.py -v` and verify it passes.

### Task 4: Agent Runner

- [ ] Add failing tests in `tests/loop/test_agent_runner.py` for item-level `agent`, `default_agent`, legacy `claude_cmd`, Codex config, and unknown agent.
- [ ] Run `python -m pytest tests/loop/test_agent_runner.py -v` and verify import failure.
- [ ] Create `scripts/loop/agent_runner.py`.
- [ ] Re-run `python -m pytest tests/loop/test_agent_runner.py -v` and verify it passes.

### Task 5: Controller Integration

- [ ] Update controller tests so `controller.py` calls `agent_runner.run_work_item(item, config)` and failure messages use the selected agent name.
- [ ] Update brainstorm controller tests so `brainstorm_controller.py` calls `agent_runner.run_brainstorm_item(item, config)`.
- [ ] Run the controller tests and verify they fail before modifying production controllers.
- [ ] Modify `scripts/loop/controller.py` and `scripts/loop/brainstorm_controller.py`.
- [ ] Re-run `python -m pytest tests/loop/test_controller.py tests/loop/test_brainstorm_controller.py -v`.

### Task 6: Full Verification

- [ ] Run `python -m pytest tests/loop -v`.
- [ ] Run `git status --short` and confirm only intended files changed.
