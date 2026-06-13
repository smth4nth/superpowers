import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import todo_queue as tq


def _write(tmp_path, items):
    f = tmp_path / "todo-items.json"
    f.write_text(json.dumps({"items": items}), encoding="utf-8")
    return str(f)


def test_next_pending_returns_first_pending(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "done"},
        {"id": "2", "status": "pending", "title": "T"},
        {"id": "3", "status": "pending", "title": "T2"},
    ])
    assert tq.next_pending(path)["id"] == "2"


def test_next_pending_returns_none_when_all_done(tmp_path):
    path = _write(tmp_path, [{"id": "1", "status": "done"}])
    assert tq.next_pending(path) is None


def test_next_pending_returns_none_when_empty(tmp_path):
    path = _write(tmp_path, [])
    assert tq.next_pending(path) is None


def test_next_pending_returns_none_when_file_missing(tmp_path):
    assert tq.next_pending(str(tmp_path / "nope.json")) is None


def test_next_pending_returns_none_on_bad_json(tmp_path):
    f = tmp_path / "todo-items.json"
    f.write_text("not json", encoding="utf-8")
    assert tq.next_pending(str(f)) is None


def test_write_done_sets_status_and_updates_timestamp(tmp_path):
    path = _write(tmp_path, [
        {"id": "1", "status": "pending", "title": "T",
         "updated_at": "2026-06-12T00:00:00Z"},
    ])
    tq.write_done({"id": "1"}, path=path)
    data = json.loads(Path(path).read_text())
    assert data["items"][0]["status"] == "done"
    assert data["items"][0]["updated_at"] != "2026-06-12T00:00:00Z"


def test_write_done_noop_when_file_missing(tmp_path):
    tq.write_done({"id": "1"}, path=str(tmp_path / "nope.json"))
    # must not raise
