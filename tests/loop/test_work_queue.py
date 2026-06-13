import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import work_queue as wq


def _write(tmp_path, items):
    f = tmp_path / "work-items.json"
    f.write_text(json.dumps({"items": items}), encoding="utf-8")
    return str(f)


def test_next_pending_returns_first_pending(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "done"},
        {"id": "2", "status": "pending", "title": "T", "description": "D"},
        {"id": "3", "status": "pending", "title": "T2", "description": "D2"},
    ])
    assert wq.next_pending(path)["id"] == "2"


def test_next_pending_skips_needs_human(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "needs_human"},
        {"id": "2", "status": "pending", "title": "T", "description": "D"},
    ])
    assert wq.next_pending(path)["id"] == "2"


def test_next_pending_returns_none_when_empty(tmp_path):
    path = _write(tmp_path, [])
    assert wq.next_pending(path) is None


def test_next_pending_returns_none_when_file_missing(tmp_path):
    assert wq.next_pending(str(tmp_path / "nope.json")) is None


def test_next_pending_returns_none_on_bad_json(tmp_path):
    f = tmp_path / "work-items.json"
    f.write_text("not json", encoding="utf-8")
    assert wq.next_pending(str(f)) is None


def test_write_needs_human_sets_status_and_blocker(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "pending", "title": "T", "description": "D",
         "blocker": None, "updated_at": "2026-06-12T00:00:00Z"},
    ])
    wq.write_needs_human({"id": "1"}, reason="exit code 1", path=path)
    data = json.loads(Path(path).read_text())
    wi = data["items"][0]
    assert wi["status"] == "needs_human"
    assert wi["blocker"]["context"] == "exit code 1"
    assert wi["updated_at"] != "2026-06-12T00:00:00Z"


def test_write_needs_human_noop_when_file_missing(tmp_path):
    wq.write_needs_human({"id": "1"}, "reason", path=str(tmp_path / "nope.json"))
    # must not raise


def test_add_item_appends_work_item(tmp_path):
    path = _write(tmp_path, [])
    todo_item = {
        "id": "1",
        "title": "Fix auth",
        "description": "Refactor auth.ts",
        "project_dir": str(tmp_path),
        "created_at": "2026-06-12T10:00:00Z",
    }
    wq.add_item(todo_item, session_id="abc-123", path=path)
    data = json.loads(Path(path).read_text())
    assert len(data["items"]) == 1
    wi = data["items"][0]
    assert wi["id"] == "1"
    assert wi["title"] == "Fix auth"
    assert wi["session_id"] == "abc-123"
    assert wi["status"] == "pending"
    assert wi["blocker"] is None
    assert wi["state_id"] is None
    assert wi["human_input"] is None


def test_add_item_copies_agent_when_present(tmp_path):
    path = _write(tmp_path, [])
    todo_item = {
        "id": "1",
        "title": "Fix auth",
        "description": "Refactor auth.ts",
        "project_dir": str(tmp_path),
        "created_at": "2026-06-12T10:00:00Z",
        "agent": "codex",
    }
    wq.add_item(todo_item, session_id="abc-123", path=path)
    data = json.loads(Path(path).read_text())
    assert data["items"][0]["agent"] == "codex"


def test_add_item_creates_file_when_missing(tmp_path):
    path = str(tmp_path / "work-items.json")
    todo_item = {
        "id": "2", "title": "T", "description": "D",
        "project_dir": str(tmp_path), "created_at": "2026-06-12T10:00:00Z",
    }
    wq.add_item(todo_item, session_id="xyz-456", path=path)
    data = json.loads(Path(path).read_text())
    assert data["items"][0]["session_id"] == "xyz-456"


def test_add_item_preserves_existing_items(tmp_path):
    path = _write(tmp_path, [
        {"id": "existing", "status": "done", "title": "old"},
    ])
    todo_item = {
        "id": "new", "title": "New", "description": "D",
        "project_dir": str(tmp_path), "created_at": "2026-06-12T10:00:00Z",
    }
    wq.add_item(todo_item, session_id="s1", path=path)
    data = json.loads(Path(path).read_text())
    assert len(data["items"]) == 2
    assert data["items"][0]["id"] == "existing"
    assert data["items"][1]["id"] == "new"
