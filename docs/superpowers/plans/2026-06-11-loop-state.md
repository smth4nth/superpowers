# Loop State & Memory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Loop State & Memory layer — extend `finishing-a-development-branch` to write a run record to `state.json` and update `work-items.json` as the final step of every loop session.

**Architecture:** The loop controller is an external program (not a skill). The only superpowers contribution is a new Step 7 at the end of `finishing-a-development-branch` that detects loop context, writes the completed run record to `~/.config/superpowers/loop/state.json`, and updates the work item status in `~/.config/superpowers/loop/work-items.json`.

**Tech Stack:** Markdown skill file. JSON file I/O via PowerShell (Windows) or Bash (Unix).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/finishing-a-development-branch/SKILL.md` | Modify | Add Step 7: write run record to state.json and update work-items.json |

---

### Task 1: Add Step 7 to `finishing-a-development-branch`

**Files:**
- Modify: `skills/finishing-a-development-branch/SKILL.md`

Insertion point: after the Step 6 (Cleanup Workspace) section, before the `## Quick Reference` table.

- [ ] **Step 1: Read the file to confirm insertion point**

Read `skills/finishing-a-development-branch/SKILL.md`. Locate the line `## Quick Reference`. Step 7 is inserted immediately before it.

- [ ] **Step 2: Insert Step 7**

Insert this block immediately before `## Quick Reference`:

````markdown
## Step 7: Write Loop State (loop sessions only)

**Only run this step if this session was started by an external loop controller** — that is, the session context includes an active work item id (`loop_item_id`) and a start timestamp (`loop_started_at`). If not in a loop session, skip this step entirely.

### Determine Outcome

| `completion.action` | `outcome` |
|---------------------|-----------|
| `merged` | `done` |
| `pr_created` | `done` |
| `kept` | `needs_human` |
| `discarded` | `done` |

### Build the Run Record

Construct the following JSON object from context accumulated throughout this session:

```json
{
  "run_id": "r-<YYYYMMDD-HHMM>",
  "item_id": "<loop_item_id from session context>",
  "outcome": "<done or needs_human per outcome table above>",
  "started_at": "<loop_started_at from session context>",
  "completed_at": "<ISO 8601 timestamp now>",

  "worktree": {
    "branch": "<branch name from Step 2 of this skill>",
    "path": "<worktree path from Step 2 of this skill>"
  },

  "spec": {
    "path": "<spec doc path written during brainstorming>",
    "commit": "<git commit SHA of the spec doc>"
  },

  "plan": {
    "path": "<plan doc path written during writing-plans>",
    "commit": "<git commit SHA of the plan doc>",
    "task_count": "<number of tasks in the plan>"
  },

  "tasks": [
    {
      "name": "<task name>",
      "implementer_status": "<DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED>",
      "implementer_concerns": "<string or null>",
      "spec_review_rounds": "<number>",
      "spec_review_result": "<passed|failed>",
      "quality_review_rounds": "<number>",
      "quality_review_result": "<passed|failed>",
      "quality_concerns": "<string or null>",
      "commits": ["<sha message>"],
      "files_changed": ["<path>"]
    }
  ],

  "final_review": "<final code reviewer overall verdict>",

  "verification": {
    "tests_passed": "<true|false>",
    "test_count": "<number>",
    "build_passed": "<true|false>"
  },

  "completion": {
    "action": "<merged|pr_created|kept|discarded>",
    "pr_url": "<url or null>",
    "branch": "<branch name>",
    "worktree_cleaned": "<true|false>"
  },

  "blocker": null
}
```

**Blocker fields — fill when `outcome == "needs_human"`, otherwise leave `null`:**

```json
{
  "stage": "<brainstorming|writing-plans|subagent-driven-development|finishing-a-development-branch>",
  "task": "<task name if blocked during subagent-driven-development, else null>",
  "implementer_status": "<BLOCKED|NEEDS_CONTEXT if applicable, else null>",
  "reason": "<what was attempted and why it got stuck>",
  "question_for_human": "<the specific question that needs answering>"
}
```

### Write to `state.json`

1. Read `~/.config/superpowers/loop/state.json`
2. Append the run record to the `runs` array
3. Write back to the same file

**PowerShell:**
```powershell
$dir   = "$env:USERPROFILE\.config\superpowers\loop"
$state = Get-Content "$dir\state.json" | ConvertFrom-Json
$state.runs = @($state.runs) + $runRecord
$state | ConvertTo-Json -Depth 20 | Out-File -Encoding utf8 "$dir\state.json"
```

**Bash:**
```bash
dir="$HOME/.config/superpowers/loop"
python3 -c "
import json
with open('$dir/state.json') as f:
    state = json.load(f)
state['runs'].append($RUN_RECORD_JSON)
with open('$dir/state.json', 'w') as f:
    json.dump(state, f, indent=2)
"
```

### Update `work-items.json`

1. Read `~/.config/superpowers/loop/work-items.json`
2. Find the item where `id == loop_item_id`
3. Apply updates:

**If `outcome == "done"`:**
- `status` → `"done"`
- `state_id` → `run_id`
- `updated_at` → now

**If `outcome == "needs_human"`:**
- `status` → `"needs_human"`
- `blocker` → `{ "question": "<question_for_human>", "context": "<reason>" }`
- `updated_at` → now
- `state_id` → leave as `null`

4. Write back to the same file.

**PowerShell:**
```powershell
$dir  = "$env:USERPROFILE\.config\superpowers\loop"
$data = Get-Content "$dir\work-items.json" | ConvertFrom-Json
$item = $data.items | Where-Object { $_.id -eq $loopItemId }
# apply status/state_id/blocker/updated_at fields to $item
$data | ConvertTo-Json -Depth 20 | Out-File -Encoding utf8 "$dir\work-items.json"
```

**Bash:**
```bash
dir="$HOME/.config/superpowers/loop"
python3 -c "
import json
from datetime import datetime, timezone
with open('$dir/work-items.json') as f:
    data = json.load(f)
item = next(i for i in data['items'] if i['id'] == '$LOOP_ITEM_ID')
# apply status/state_id/blocker/updated_at fields to item
with open('$dir/work-items.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

### Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Loop state written
  Run:     <run_id>
  Item:    #<id> <title>
  Outcome: <done | needs_human>
  [If needs_human]: Human input needed: <question_for_human>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
````

- [ ] **Step 3: Verify the insertion**

Read `skills/finishing-a-development-branch/SKILL.md` and confirm:
- `## Step 7` appears after the `## Step 6` block and before `## Quick Reference`
- Run record JSON contains all fields from the spec: `run_id`, `item_id`, `outcome`, `started_at`, `completed_at`, `worktree`, `spec`, `plan`, `tasks`, `final_review`, `verification`, `completion`, `blocker`
- Outcome mapping covers all four `completion.action` values
- Both PowerShell and Bash variants are present for both file writes
- Step 7 does NOT re-invoke `superpowers:loop` (loop control is external)

- [ ] **Step 4: Commit**

```bash
git add skills/finishing-a-development-branch/SKILL.md
git commit -m "feat: write loop state at end of finishing-a-development-branch"
```
