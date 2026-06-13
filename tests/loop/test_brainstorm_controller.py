import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("watchdog", MagicMock())
sys.modules.setdefault("watchdog.events", MagicMock())
sys.modules.setdefault("watchdog.observers", MagicMock())

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import brainstorm_controller as bc_mod
from brainstorm_controller import BrainstormController


def _ctrl():
    return BrainstormController(config={"claude_cmd": "claude"})


def test_drain_queue_processes_pending_item(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "work_queue") as mock_wq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs:
        mock_tq.next_pending.side_effect = [item, None]
        mock_bs.run.return_value = "session-abc"
        _ctrl()._drain_queue()
    mock_bs.run.assert_called_once()
    mock_wq.add_item.assert_called_once_with(item, "session-abc")
    mock_tq.write_done.assert_called_once_with(item)


def test_drain_queue_skips_when_session_id_is_none(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "work_queue") as mock_wq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs:
        mock_tq.next_pending.side_effect = [item, None]
        mock_bs.run.return_value = None
        _ctrl()._drain_queue()
    mock_wq.add_item.assert_not_called()
    mock_tq.write_done.assert_not_called()


def test_drain_queue_processes_multiple_items(tmp_path):
    item1 = {"id": "1", "title": "T1", "description": "D", "project_dir": str(tmp_path)}
    item2 = {"id": "2", "title": "T2", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "work_queue") as mock_wq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs:
        mock_tq.next_pending.side_effect = [item1, item2, None]
        mock_bs.run.return_value = "sess"
        _ctrl()._drain_queue()
    assert mock_bs.run.call_count == 2
    assert mock_wq.add_item.call_count == 2


def test_drain_queue_breaks_loop_on_repeated_item(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "work_queue") as mock_wq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs:
        mock_tq.next_pending.return_value = item
        mock_bs.run.return_value = None  # always fails
        _ctrl()._drain_queue()
    assert mock_bs.run.call_count == 1


def test_on_file_changed_sets_wake_event():
    c = _ctrl()
    assert not c._wake.is_set()
    c.on_file_changed()
    assert c._wake.is_set()


def test_drain_queue_passes_claude_cmd_to_brainstorm_session(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(bc_mod, "todo_queue") as mock_tq, \
         patch.object(bc_mod, "work_queue") as mock_wq, \
         patch.object(bc_mod, "brainstorm_session") as mock_bs:
        mock_tq.next_pending.side_effect = [item, None]
        mock_bs.run.return_value = "sess"
        BrainstormController(config={"claude_cmd": "/usr/local/bin/claude"})._drain_queue()
    mock_bs.run.assert_called_once_with(item, claude_cmd="/usr/local/bin/claude")
