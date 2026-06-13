import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import agent_runner


def _item(**kwargs):
    base = {"id": "1", "title": "T", "description": "D", "project_dir": "/tmp/proj"}
    base.update(kwargs)
    return base


def test_work_item_defaults_to_claude_with_legacy_config():
    with patch.object(agent_runner, "session") as mock_claude:
        mock_claude.run.return_value = 0
        result = agent_runner.run_work_item(_item(), {"claude_cmd": "/bin/claude"})
    assert result == 0
    mock_claude.run.assert_called_once_with(_item(), claude_cmd="/bin/claude")


def test_work_item_uses_codex_when_item_agent_is_codex():
    item = _item(agent="codex")
    config = {"agents": {"codex": {"cmd": "/bin/codex"}}}
    with patch.object(agent_runner, "codex_session") as mock_codex:
        mock_codex.run.return_value = 0
        result = agent_runner.run_work_item(item, config)
    assert result == 0
    mock_codex.run.assert_called_once_with(item, codex_cmd="/bin/codex")


def test_work_item_uses_default_agent_when_item_omits_agent():
    config = {"default_agent": "codex", "agents": {"codex": {"cmd": "codex-dev"}}}
    with patch.object(agent_runner, "codex_session") as mock_codex:
        mock_codex.run.return_value = 0
        result = agent_runner.run_work_item(_item(), config)
    assert result == 0
    mock_codex.run.assert_called_once_with(_item(), codex_cmd="codex-dev")


def test_work_item_unknown_agent_returns_error_without_dispatch():
    with patch.object(agent_runner, "session") as mock_claude, \
         patch.object(agent_runner, "codex_session") as mock_codex:
        result = agent_runner.run_work_item(_item(agent="bad"), {})
    assert result == -3
    mock_claude.run.assert_not_called()
    mock_codex.run.assert_not_called()


def test_brainstorm_item_dispatches_to_claude_by_default():
    item = _item()
    with patch.object(agent_runner, "brainstorm_session") as mock_claude:
        mock_claude.run.return_value = "sess"
        result = agent_runner.run_brainstorm_item(item, {"claude_cmd": "claude-dev"})
    assert result == "sess"
    mock_claude.run.assert_called_once_with(item, claude_cmd="claude-dev")


def test_brainstorm_item_dispatches_to_codex():
    item = _item(agent="codex")
    config = {"agents": {"codex": {"cmd": "codex-dev"}}}
    with patch.object(agent_runner, "codex_brainstorm_session") as mock_codex:
        mock_codex.run.return_value = "sess"
        result = agent_runner.run_brainstorm_item(item, config)
    assert result == "sess"
    mock_codex.run.assert_called_once_with(item, codex_cmd="codex-dev")


def test_brainstorm_item_unknown_agent_returns_none():
    result = agent_runner.run_brainstorm_item(_item(agent="bad"), {})
    assert result is None


def test_agent_name_returns_item_agent_before_default():
    config = {"default_agent": "claude"}
    assert agent_runner.agent_name(_item(agent="codex"), config) == "codex"
