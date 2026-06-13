import json
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT = (
    Path.home() / ".config" / "superpowers" / "loop"
    / "todo-items" / "todo-items.json"
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


def write_done(item, path=None):
    p = Path(path) if path else _DEFAULT
    if not p.exists():
        return
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for ti in data.get("items", []):
            if ti["id"] == item["id"]:
                ti["status"] = "done"
                ti["updated_at"] = (
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                )
                break
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except (json.JSONDecodeError, KeyError, OSError):
        pass
