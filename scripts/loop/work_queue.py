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


def add_item(todo_item, session_id, path=None):
    p = Path(path) if path else _DEFAULT
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"items": []}, indent=2), encoding="utf-8")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        work_item = {
            "id": todo_item["id"],
            "title": todo_item["title"],
            "description": todo_item["description"],
            "project_dir": todo_item["project_dir"],
            "status": "pending",
            "session_id": session_id,
            "created_at": todo_item.get("created_at", now),
            "updated_at": now,
            "blocker": None,
            "human_input": None,
            "state_id": None,
        }
        if todo_item.get("agent"):
            work_item["agent"] = todo_item["agent"]
        data["items"].append(work_item)
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, KeyError, OSError):
        pass
