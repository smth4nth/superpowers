# Loop State & Memory — Design Spec

**Goal:** Persist loop execution state across sessions so each loop run can continue from where the previous one left off.

**Context:** This is the State/Memory layer of a Loop Engineering workflow built on superpowers. The loop processes work items one at a time. Each session handles one item, then ends. The next session reads state to know what's pending, what's done, and what needs human input.

---

## Two Files

### `~/.config/superpowers/loop/work-items.json`

Human-managed task queue. The human edits this file directly to add tasks and to resolve blocked items.

The loop controller reads this file to pick the next item, and writes back `status` and `state_id` when an item completes or blocks.

```json
{
  "items": [
    {
      "id": "1",
      "title": "重构 auth 模块",
      "description": "把 auth.ts 拆成独立的 session / token 两个模块",
      "status": "pending",
      "created_at": "2026-06-11T10:00:00Z",
      "updated_at": "2026-06-11T10:00:00Z",
      "blocker": null,
      "human_input": null,
      "state_id": null
    }
  ]
}
```

**Item fields:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, human-assigned |
| `title` | string | One-line description |
| `description` | string | Full task description with any context the loop needs |
| `status` | enum | See status machine below |
| `created_at` | ISO 8601 | When human created the item |
| `updated_at` | ISO 8601 | Last time loop or human modified the item |
| `blocker` | object\|null | Filled by loop when status becomes `needs_human` |
| `blocker.question` | string | What the loop needs the human to decide |
| `blocker.context` | string | What was attempted and why it got stuck |
| `human_input` | string\|null | Human's answer — filled by human when resolving a blocker |
| `state_id` | string\|null | Points to the run record in `state.json` — filled when done |

**Status machine:**

```
pending
  → (loop picks item)
  → done          : loop writes state_id, sets updated_at
  → needs_human   : loop writes blocker, sets updated_at

needs_human
  → (human fills human_input, sets status back to pending)
  → pending
```

**Loop pick order:** First `pending` item by array position (FIFO). Items with `needs_human` are skipped until the human resolves them.

---

### `~/.config/superpowers/loop/state.json`

Loop-managed execution log. The loop controller writes to this file. The human reads it for traceability. One run record per completed or blocked session.

```json
{
  "runs": [
    {
      "run_id": "r1",
      "item_id": "1",
      "outcome": "done",
      "started_at": "2026-06-11T10:05:00Z",
      "completed_at": "2026-06-11T10:47:00Z",

      "worktree": {
        "branch": "feat/auth-refactor",
        "path": ".worktrees/feat/auth-refactor"
      },

      "spec": {
        "path": "docs/superpowers/specs/2026-06-11-auth-refactor-design.md",
        "commit": "abc123"
      },

      "plan": {
        "path": "docs/superpowers/plans/2026-06-11-auth-refactor.md",
        "commit": "def456",
        "task_count": 4
      },

      "tasks": [
        {
          "name": "Task 1: Split session and token",
          "implementer_status": "DONE",
          "implementer_concerns": null,
          "spec_review_rounds": 1,
          "spec_review_result": "passed",
          "quality_review_rounds": 2,
          "quality_review_result": "passed",
          "quality_concerns": "TokenManager 有点大，非阻塞",
          "commits": ["abc123 feat: split auth module"],
          "files_changed": ["src/auth/session.ts", "src/auth/token.ts"]
        }
      ],

      "final_review": "all requirements met, ready to merge",

      "verification": {
        "tests_passed": true,
        "test_count": 42,
        "build_passed": true
      },

      "completion": {
        "action": "pr_created",
        "pr_url": "https://github.com/org/repo/pull/234",
        "branch": "feat/auth-refactor",
        "worktree_cleaned": false
      },

      "blocker": null
    }
  ]
}
```

**Run record fields:**

| Field | Description |
|-------|-------------|
| `run_id` | Unique run identifier |
| `item_id` | References the work item in `work-items.json` |
| `outcome` | `done` or `needs_human` |
| `started_at` / `completed_at` | Session timestamps |
| `worktree.branch` | Git branch used for this run |
| `worktree.path` | Worktree path on disk |
| `spec.path` | Path to brainstorming spec doc |
| `spec.commit` | Commit SHA of the spec doc |
| `plan.path` | Path to implementation plan |
| `plan.commit` | Commit SHA of the plan |
| `plan.task_count` | Number of tasks in the plan |
| `tasks[]` | Per-task execution record (see below) |
| `tasks[].implementer_status` | `DONE` / `DONE_WITH_CONCERNS` / `NEEDS_CONTEXT` / `BLOCKED` |
| `tasks[].implementer_concerns` | Concerns flagged by implementer (if DONE_WITH_CONCERNS) |
| `tasks[].spec_review_rounds` | How many review rounds until spec passed |
| `tasks[].spec_review_result` | `passed` or `failed` |
| `tasks[].quality_review_rounds` | How many review rounds until quality passed |
| `tasks[].quality_review_result` | `passed` or `failed` |
| `tasks[].quality_concerns` | Non-blocking concerns noted by reviewer |
| `tasks[].commits` | Commits made during this task |
| `tasks[].files_changed` | Files touched during this task |
| `final_review` | Final code reviewer's overall verdict |
| `verification.tests_passed` | Whether tests passed at completion |
| `verification.test_count` | Total test count |
| `verification.build_passed` | Whether build passed |
| `completion.action` | `merged`, `pr_created`, `kept`, `discarded` |
| `completion.pr_url` | PR URL if action is `pr_created` |
| `completion.branch` | Branch name |
| `completion.worktree_cleaned` | Whether worktree was removed |
| `blocker` | Filled when outcome is `needs_human` (see below) |

**Blocker fields (outcome: needs_human):**

| Field | Description |
|-------|-------------|
| `blocker.stage` | Which skill stage blocked: `brainstorming`, `writing-plans`, `subagent-driven-development`, `finishing-a-development-branch` |
| `blocker.task` | Task name if blocked during subagent-driven-development |
| `blocker.implementer_status` | Implementer's reported status (`BLOCKED` / `NEEDS_CONTEXT`) |
| `blocker.reason` | What was attempted and why it failed |
| `blocker.question_for_human` | The specific question the loop needs answered |

---

## Bidirectional Link

- `work-items.json` item `state_id` → `state.json` run `run_id`
- `state.json` run `item_id` → `work-items.json` item `id`

Both fields are set when a run completes (outcome `done`). For `needs_human` runs, `state_id` on the work item is not set — the work item stays in the queue for retry.

---

## Controller Behavior

```
Read work-items.json
→ Find first item where status == "pending"
    → None found:
        Report queue empty. List any needs_human items for human review.
        End session.
    → Found:
        Run full superpowers skill chain:
          brainstorming → writing-plans → subagent-driven-development → finishing-a-development-branch
        
        On success:
          1. Append run record to state.json (outcome: "done")
          2. Update work item: status = "done", state_id = run_id, updated_at = now
        
        On block:
          1. Append run record to state.json (outcome: "needs_human")
          2. Update work item: status = "needs_human", blocker = {question, context}, updated_at = now
          3. Pick next pending item and continue
```

---

## Storage Location

Both files live at `~/.config/superpowers/loop/` — outside the project directory, not tracked by git. This mirrors the existing auto-memory pattern (`~/.claude/projects/.../memory/`).

The loop controller receives the config dir path as part of its session context.
