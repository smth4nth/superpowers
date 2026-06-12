# Loop State & Memory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Loop State & Memory layer — a JSON-based persistence system that lets each loop session continue from where the previous one left off.

**Architecture:** Two components: (1) a new `loop` skill that picks the next pending work item from `work-items.json` and drives the full skill chain, and (2) a new Step 7 appended to `finishing-a-development-branch` that writes the completed run record to `state.json` and updates `work-items.json`, then re-invokes `superpowers:loop` to process the next item.

**Tech Stack:** Markdown skill files. JSON file I/O via PowerShell (Windows) or Bash (Unix).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/loop/SKILL.md` | Create | Loop controller — initializes files, picks next pending item, drives brainstorming → ... → finishing-a-development-branch |
| `skills/finishing-a-development-branch/SKILL.md` | Modify | Add Step 7: write run record to state.json, update work-items.json, re-invoke loop |

---

### Task 1: Create `skills/loop/SKILL.md`

**Files:**
- Create: `skills/loop/SKILL.md`

- [ ] **Step 1: Create the skill file with this exact content**

```markdown
---
name: loop
description: Use when you want to process work items from the loop queue — initializes state files if needed, picks the next pending item from work-items.json, and drives the full brainstorming → writing-plans → subagent-driven-development → finishing-a-development-branch chain
---

# Loop

Process the next pending work item from `~/.config/superpowers/loop/`.

**Announce at start:** "I'm using the loop skill to process the next work item."

## Step 0: Initialize State Files

Ensure `~/.config/superpowers/loop/` exists with both required JSON files.

**PowerShell:**
```powershell
$dir = "$env:USERPROFILE\.config\superpowers\loop"
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir }
$wf = "$dir\work-items.json"
if (-not (Test-Path $wf)) { '{"items":[]}' | Out-File -Encoding utf8 $wf }
$sf = "$dir\state.json"
if (-not (Test-Path $sf)) { '{"runs":[]}' | Out-File -Encoding utf8 $sf }
```

**Bash:**
```bash
dir="$HOME/.config/superpowers/loop"
mkdir -p "$dir"
[ -f "$dir/work-items.json" ] || echo '{"items":[]}' > "$dir/work-items.json"
[ -f "$dir/state.json" ]      || echo '{"runs":[]}'  > "$dir/state.json"
```

## Step 1: Pick Next Pending Item

Read `work-items.json`. Find the first item where `status == "pending"` (FIFO by array position).

**PowerShell:**
```powershell
$dir  = "$env:USERPROFILE\.config\superpowers\loop"
$data = Get-Content "$dir\work-items.json" | ConvertFrom-Json
$item = $data.items | Where-Object { $_.status -eq "pending" } | Select-Object -First 1
```

**Bash:**
```bash
dir="$HOME/.config/superpowers/loop"
item_json=$(python3 -c "
import json
data = json.load(open('$dir/work-items.json'))
item = next((i for i in data['items'] if i['status'] == 'pending'), None)
print(json.dumps(item) if item else 'null')
")
```

**If no pending item found**, report and stop:

```
Queue is empty — no pending work items.

Needs-human items waiting for your input:
  - #<id>: <title>
    Question: <blocker.question>
    Context:  <blocker.context>

Add items to ~/.config/superpowers/loop/work-items.json to continue.
```

**If a pending item is found**, continue to Step 2.

## Step 2: Note Loop Context

Record the active item and start time in session context. All downstream skills share this context.

Announce:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Loop item #<id>: <title>
<description>
[If human_input is not null: "Resuming with human input: <human_input>"]
Started: <ISO 8601 timestamp — note this as loop_started_at>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Step 3: Run Skill Chain

**REQUIRED: Invoke `superpowers:brainstorming`**

The work item title and description define what to build. If `human_input` is set, pass it as additional context for brainstorming (it is the human's answer to a previous blocker).

The chain auto-continues:
`brainstorming` → `writing-plans` → `subagent-driven-development` → `finishing-a-development-branch`

`finishing-a-development-branch` Step 7 will detect the loop context, write state, and invoke `superpowers:loop` again to process the next item.
```

- [ ] **Step 2: Verify the file exists and frontmatter is valid**

```bash
head -5 skills/loop/SKILL.md
```

Expected output:
```
---
name: loop
description: Use when you want to process work items from the loop queue...
---
```

- [ ] **Step 3: Commit**

```bash
git add skills/loop/SKILL.md
git commit -m "feat: add loop skill for work item queue processing"
```

---

### Task 2: Add Step 7 to `finishing-a-development-branch`

**Files:**
- Modify: `skills/finishing-a-development-branch/SKILL.md`

The insertion point is after the Step 6 (Cleanup Workspace) section and before the `## Quick Reference` table.

- [ ] **Step 1: Read the file to locate insertion point**

Read `skills/finishing-a-development-branch/SKILL.md`. Find the line that reads `## Quick Reference`. Step 7 is inserted immediately before it.

- [ ] **Step 2: Insert Step 7 before `## Quick Reference`**

Insert this block immediately before the `## Quick Reference` heading:

```markdown
## Step 7: Write Loop State (loop sessions only)

**Only run this step if the session was started by `superpowers:loop`** — that is, there is an active loop item in session context with a `loop_started_at` timestamp. If not in a loop session, skip this step entirely.

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
  "item_id": "<loop item id from Step 2 of loop skill>",
  "outcome": "<done or needs_human per outcome table above>",
  "started_at": "<loop_started_at from Step 2 of loop skill>",
  "completed_at": "<ISO 8601 timestamp now>",

  "worktree": {
    "branch": "<branch detected in Step 2 of this skill>",
    "path": "<worktree path detected in Step 2 of this skill>"
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

  "blocker": "<null if outcome is done — see blocker fields below if outcome is needs_human>"
}
```

**Blocker fields (outcome `needs_human` only):**

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
2. Parse JSON, append the run record to the `runs` array
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
python3 << EOF
import json
with open('$dir/state.json') as f:
    state = json.load(f)
state['runs'].append($RUN_RECORD_JSON)
with open('$dir/state.json', 'w') as f:
    json.dump(state, f, indent=2)
EOF
```

### Update `work-items.json`

1. Read `~/.config/superpowers/loop/work-items.json`
2. Find the item where `id == loop item id`
3. Apply updates per outcome:

**If `outcome == "done"`:**
- `status` → `"done"`
- `state_id` → `run_id`
- `updated_at` → now
- `blocker` → leave as-is (null)

**If `outcome == "needs_human"`:**
- `status` → `"needs_human"`
- `blocker` → `{ "question": "<question_for_human>", "context": "<reason>" }`
- `updated_at` → now
- `state_id` → leave as `null` (item stays in queue for retry once human resolves)

4. Write back to the same file.

### Report and Continue

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Loop state written
  Run:    <run_id>
  Item:   #<id> <title>
  Outcome: <done | needs_human>
  [If needs_human: "Blocked — human input needed: <question_for_human>"]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**REQUIRED: Invoke `superpowers:loop`** to pick and process the next pending item.

```

- [ ] **Step 3: Verify the insertion**

Read `skills/finishing-a-development-branch/SKILL.md` and confirm:
- `## Step 7` appears after `## Step 6` and before `## Quick Reference`
- The run record JSON contains all fields from the spec: `run_id`, `item_id`, `outcome`, `started_at`, `completed_at`, `worktree`, `spec`, `plan`, `tasks`, `final_review`, `verification`, `completion`, `blocker`
- Outcome mapping table covers all four `completion.action` values
- Both PowerShell and Bash variants are present for both file writes
- Step 7 ends with "Invoke `superpowers:loop`"

- [ ] **Step 4: Commit**

```bash
git add skills/finishing-a-development-branch/SKILL.md
git commit -m "feat: write loop state at end of finishing-a-development-branch"
```
