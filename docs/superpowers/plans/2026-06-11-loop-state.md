# Loop State & Memory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Loop State & Memory layer — extend `finishing-a-development-branch` to write a per-session state file and update the work item queue as the final step of every loop session.

**Architecture:** The loop controller is an external program (not a skill). The only superpowers contribution is a new Step 7 at the end of `finishing-a-development-branch` that: (1) generates a UUID, (2) writes the run record as `~/.config/superpowers/loop/state/<uuid>.json`, and (3) updates the work item in `~/.config/superpowers/loop/work-items/work-items.json`.

**Tech Stack:** Markdown skill file. JSON file I/O via PowerShell (Windows) or Bash (Unix).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/finishing-a-development-branch/SKILL.md` | Modify | Add Step 7: generate UUID, write `state/<uuid>.json`, update `work-items/work-items.json` |

---

### Task 1: Add Step 7 to `finishing-a-development-branch`

**Files:**
- Modify: `skills/finishing-a-development-branch/SKILL.md`

Insertion point: after the Step 6 (Cleanup Workspace) section, immediately before `## Quick Reference`.

- [ ] **Step 1: Read the file to confirm insertion point**

Read `skills/finishing-a-development-branch/SKILL.md`. Locate `## Quick Reference`. Step 7 is inserted immediately before it.

- [ ] **Step 2: Insert Step 7**

Insert this block immediately before `## Quick Reference`:

````markdown
## Step 7: Write Loop State (loop sessions only)

**Only run this step if this session was started by an external loop controller** — that is, the session context includes an active work item id (`loop_item_id`) and a start timestamp (`loop_started_at`). If not in a loop session, skip this step entirely.

### Generate UUID

Generate a UUID for this session. This UUID is both the `run_id` field and the state file name.

**PowerShell:**
```powershell
$uuid = [System.Guid]::NewGuid().ToString()
```

**Bash:**
```bash
uuid=$(python3 -c "import uuid; print(uuid.uuid4())")
```

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
  "run_id": "<uuid>",
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

### Write `state/<uuid>.json`

Ensure the `state/` directory exists, then write the run record as a new file.

**PowerShell:**
```powershell
$base = "$env:USERPROFILE\.config\superpowers\loop"
$stateDir = "$base\state"
if (-not (Test-Path $stateDir)) { New-Item -ItemType Directory -Force $stateDir }
$runRecord | ConvertTo-Json -Depth 20 | Out-File -Encoding utf8 "$stateDir\$uuid.json"
```

**Bash:**
```bash
base="$HOME/.config/superpowers/loop"
mkdir -p "$base/state"
echo "$RUN_RECORD_JSON" | python3 -c "
import json, sys
print(json.dumps(json.load(sys.stdin), indent=2))
" > "$base/state/$uuid.json"
```

### Update `work-items/work-items.json`

1. Read `~/.config/superpowers/loop/work-items/work-items.json`
2. Find the item where `id == loop_item_id`
3. Apply updates:

**If `outcome == "done"`:**
- `status` → `"done"`
- `state_id` → `<uuid>`
- `updated_at` → now

**If `outcome == "needs_human"`:**
- `status` → `"needs_human"`
- `blocker` → `{ "question": "<question_for_human>", "context": "<reason>" }`
- `updated_at` → now
- `state_id` → leave as `null`

4. Write back to the same file.

**PowerShell:**
```powershell
$base = "$env:USERPROFILE\.config\superpowers\loop"
$data = Get-Content "$base\work-items\work-items.json" | ConvertFrom-Json
$item = $data.items | Where-Object { $_.id -eq $loopItemId }
# apply status / state_id / blocker / updated_at to $item
$data | ConvertTo-Json -Depth 20 | Out-File -Encoding utf8 "$base\work-items\work-items.json"
```

**Bash:**
```bash
base="$HOME/.config/superpowers/loop"
python3 -c "
import json
from datetime import datetime, timezone
with open('$base/work-items/work-items.json') as f:
    data = json.load(f)
item = next(i for i in data['items'] if i['id'] == '$LOOP_ITEM_ID')
# apply status / state_id / blocker / updated_at to item
with open('$base/work-items/work-items.json', 'w') as f:
    json.dump(data, f, indent=2)
"
```

### Report

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Loop state written
  Run:     <uuid>
  Item:    #<id> <title>
  Outcome: <done | needs_human>
  [If needs_human]: Human input needed: <question_for_human>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
````

- [ ] **Step 3: Verify the insertion**

Read `skills/finishing-a-development-branch/SKILL.md` and confirm:
- `## Step 7` appears after `## Step 6` and before `## Quick Reference`
- UUID generation is present for both PowerShell and Bash
- Run record JSON contains all spec fields: `run_id`, `item_id`, `outcome`, `started_at`, `completed_at`, `worktree`, `spec`, `plan`, `tasks`, `final_review`, `verification`, `completion`, `blocker`
- State is written to `state/<uuid>.json` (new file), not appended to a shared file
- work-items is updated at `work-items/work-items.json`
- Outcome mapping covers all four `completion.action` values
- Step 7 does NOT re-invoke `superpowers:loop` (loop control is external)

- [ ] **Step 4: Commit**

```bash
git add skills/finishing-a-development-branch/SKILL.md
git commit -m "feat: write loop state at end of finishing-a-development-branch"
```
