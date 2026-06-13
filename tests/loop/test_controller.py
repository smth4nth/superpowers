import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Stub out watchdog before importing controller
sys.modules.setdefault("watchdog", MagicMock())
sys.modules.setdefault("watchdog.events", MagicMock())
sys.modules.setdefault("watchdog.observers", MagicMock())

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import controller as ctrl_mod
from controller import Controller


def _ctrl():
    return Controller(config={"claude_cmd": "claude"})


def test_drain_queue_processes_pending_item(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "agent_runner") as mock_runner:
        mock_q.next_pending.side_effect = [item, None]
        mock_runner.run_work_item.return_value = 0
        _ctrl()._drain_queue()
    mock_runner.run_work_item.assert_called_once_with(item, {"claude_cmd": "claude"})


def test_drain_queue_writes_needs_human_on_nonzero_exit(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "agent_runner") as mock_runner:
        mock_q.next_pending.side_effect = [item, None]
        mock_runner.run_work_item.return_value = 2
        _ctrl()._drain_queue()
    mock_q.write_needs_human.assert_called_once_with(
        item, reason="claude exited with code 2"
    )


def test_drain_queue_writes_needs_human_on_missing_project_dir():
    item = {"id": "1", "title": "T", "description": "D", "project_dir": "/nope"}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "agent_runner") as mock_runner:
        mock_q.next_pending.side_effect = [item, None]
        mock_runner.run_work_item.return_value = -1
        _ctrl()._drain_queue()
    mock_q.write_needs_human.assert_called_once_with(
        item, reason="project_dir not found: /nope"
    )


def test_drain_queue_processes_multiple_items(tmp_path):
    item1 = {"id": "1", "title": "T1", "description": "D", "project_dir": str(tmp_path)}
    item2 = {"id": "2", "title": "T2", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "agent_runner") as mock_runner:
        mock_q.next_pending.side_effect = [item1, item2, None]
        mock_runner.run_work_item.return_value = 0
        _ctrl()._drain_queue()
    assert mock_runner.run_work_item.call_count == 2


def test_on_file_changed_sets_wake_event():
    c = _ctrl()
    assert not c._wake.is_set()
    c.on_file_changed()
    assert c._wake.is_set()


def test_drain_queue_breaks_loop_on_repeated_item(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path)}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "agent_runner") as mock_runner:
        # next_pending always returns the same item (write_needs_human silently failed)
        mock_q.next_pending.return_value = item
        mock_runner.run_work_item.return_value = 1
        _ctrl()._drain_queue()
    # session.run should be called exactly once despite infinite queue
    assert mock_runner.run_work_item.call_count == 1


def test_drain_queue_writes_needs_human_on_missing_claude_cmd():
    item = {"id": "1", "title": "T", "description": "D", "project_dir": "/nope"}
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "agent_runner") as mock_runner:
        mock_q.next_pending.side_effect = [item, None]
        mock_runner.run_work_item.return_value = -2
        _ctrl()._drain_queue()
    mock_q.write_needs_human.assert_called_once_with(
        item, reason="claude binary not found: claude"
    )


def test_drain_queue_writes_needs_human_on_unknown_agent(tmp_path):
    item = {
        "id": "1",
        "title": "T",
        "description": "D",
        "project_dir": str(tmp_path),
        "agent": "bad",
    }
    with patch.object(ctrl_mod, "work_queue") as mock_q, \
         patch.object(ctrl_mod, "agent_runner") as mock_runner:
        mock_q.next_pending.side_effect = [item, None]
        mock_runner.run_work_item.return_value = -3
        _ctrl()._drain_queue()
    mock_q.write_needs_human.assert_called_once_with(
        item, reason="unknown agent: bad"
    )
