---
name: finishing-a-development-branch
description: Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides completion of development work by presenting structured options for merge, PR, or cleanup
---

# Finishing a Development Branch

## Overview

Guide completion of development work by presenting clear options and handling chosen workflow.

**Core principle:** Verify tests → Detect environment → Present options → Execute choice → Clean up.

**Announce at start:** "I'm using the finishing-a-development-branch skill to complete this work."

## The Process

### Step 1: Verify Tests

**Before presenting options, verify tests pass:**

```bash
# Run project's test suite
npm test / cargo test / pytest / go test ./...
```

**If tests fail:**
```
Tests failing (<N> failures). Must fix before completing:

[Show failures]

Cannot proceed with merge/PR until tests pass.
```

Stop. Don't proceed to Step 2.

**If tests pass:** Continue to Step 2.

### Step 2: Detect Environment

**Determine workspace state before presenting options:**

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
```

This determines which menu to show and how cleanup works:

| State | Menu | Cleanup |
|-------|------|---------|
| `GIT_DIR == GIT_COMMON` (normal repo) | Standard 4 options | No worktree to clean up |
| `GIT_DIR != GIT_COMMON`, named branch | Standard 4 options | Provenance-based (see Step 6) |
| `GIT_DIR != GIT_COMMON`, detached HEAD | Reduced 3 options (no merge) | No cleanup (externally managed) |

### Step 3: Determine Base Branch

```bash
# Try common base branches
git merge-base HEAD main 2>/dev/null || git merge-base HEAD master 2>/dev/null
```

Or ask: "This branch split from main - is that correct?"

### Step 4: Present Options

**Normal repo and named-branch worktree — present exactly these 4 options:**

```
Implementation complete. What would you like to do?

1. Merge back to <base-branch> locally
2. Push and create a Pull Request
3. Keep the branch as-is (I'll handle it later)
4. Discard this work

Which option?
```

**Detached HEAD — present exactly these 3 options:**

```
Implementation complete. You're on a detached HEAD (externally managed workspace).

1. Push as new branch and create a Pull Request
2. Keep as-is (I'll handle it later)
3. Discard this work

Which option?
```

**Don't add explanation** - keep options concise.

### Step 5: Execute Choice

#### Option 1: Merge Locally

```bash
# Get main repo root for CWD safety
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"

# Merge first — verify success before removing anything
git checkout <base-branch>
git pull
git merge <feature-branch>

# Verify tests on merged result
<test command>

# Only after merge succeeds: cleanup worktree (Step 6), then delete branch
```

Then: Cleanup worktree (Step 6), then delete branch:

```bash
git branch -d <feature-branch>
```

#### Option 2: Push and Create PR

```bash
# Push branch
git push -u origin <feature-branch>

# Create PR
gh pr create --title "<title>" --body "$(cat <<'EOF'
## Summary
<2-3 bullets of what changed>

## Test Plan
- [ ] <verification steps>
EOF
)"
```

**Do NOT clean up worktree** — user needs it alive to iterate on PR feedback.

#### Option 3: Keep As-Is

Report: "Keeping branch <name>. Worktree preserved at <path>."

**Don't cleanup worktree.**

#### Option 4: Discard

**Confirm first:**
```
This will permanently delete:
- Branch <name>
- All commits: <commit-list>
- Worktree at <path>

Type 'discard' to confirm.
```

Wait for exact confirmation.

If confirmed:
```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
```

Then: Cleanup worktree (Step 6), then force-delete branch:
```bash
git branch -D <feature-branch>
```

### Step 6: Cleanup Workspace

**Only runs for Options 1 and 4.** Options 2 and 3 always preserve the worktree.

```bash
GIT_DIR=$(cd "$(git rev-parse --git-dir)" 2>/dev/null && pwd -P)
GIT_COMMON=$(cd "$(git rev-parse --git-common-dir)" 2>/dev/null && pwd -P)
WORKTREE_PATH=$(git rev-parse --show-toplevel)
```

**If `GIT_DIR == GIT_COMMON`:** Normal repo, no worktree to clean up. Done.

**If worktree path is under `.worktrees/`, `worktrees/`, or `~/.config/superpowers/worktrees/`:** Superpowers created this worktree — we own cleanup.

```bash
MAIN_ROOT=$(git -C "$(git rev-parse --git-common-dir)/.." rev-parse --show-toplevel)
cd "$MAIN_ROOT"
git worktree remove "$WORKTREE_PATH"
git worktree prune  # Self-healing: clean up any stale registrations
```

**Otherwise:** The host environment (harness) owns this workspace. Do NOT remove it. If your platform provides a workspace-exit tool, use it. Otherwise, leave the workspace in place.

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

## Quick Reference

| Option | Merge | Push | Keep Worktree | Cleanup Branch |
|--------|-------|------|---------------|----------------|
| 1. Merge locally | yes | - | - | yes |
| 2. Create PR | - | yes | yes | - |
| 3. Keep as-is | - | - | yes | - |
| 4. Discard | - | - | - | yes (force) |

## Common Mistakes

**Skipping test verification**
- **Problem:** Merge broken code, create failing PR
- **Fix:** Always verify tests before offering options

**Open-ended questions**
- **Problem:** "What should I do next?" is ambiguous
- **Fix:** Present exactly 4 structured options (or 3 for detached HEAD)

**Cleaning up worktree for Option 2**
- **Problem:** Remove worktree user needs for PR iteration
- **Fix:** Only cleanup for Options 1 and 4

**Deleting branch before removing worktree**
- **Problem:** `git branch -d` fails because worktree still references the branch
- **Fix:** Merge first, remove worktree, then delete branch

**Running git worktree remove from inside the worktree**
- **Problem:** Command fails silently when CWD is inside the worktree being removed
- **Fix:** Always `cd` to main repo root before `git worktree remove`

**Cleaning up harness-owned worktrees**
- **Problem:** Removing a worktree the harness created causes phantom state
- **Fix:** Only clean up worktrees under `.worktrees/`, `worktrees/`, or `~/.config/superpowers/worktrees/`

**No confirmation for discard**
- **Problem:** Accidentally delete work
- **Fix:** Require typed "discard" confirmation

## Red Flags

**Never:**
- Proceed with failing tests
- Merge without verifying tests on result
- Delete work without confirmation
- Force-push without explicit request
- Remove a worktree before confirming merge success
- Clean up worktrees you didn't create (provenance check)
- Run `git worktree remove` from inside the worktree

**Always:**
- Verify tests before offering options
- Detect environment before presenting menu
- Present exactly 4 options (or 3 for detached HEAD)
- Get typed confirmation for Option 4
- Clean up worktree for Options 1 & 4 only
- `cd` to main repo root before worktree removal
- Run `git worktree prune` after removal
