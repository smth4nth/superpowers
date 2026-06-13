import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import codex_session


def _item(tmp_path, **kwargs):
    base = {
        "id": "1",
        "title": "Fix auth bug",
        "description": "Refactor auth.ts into two modules",
        "project_dir": str(tmp_path),
    }
    base.update(kwargs)
    return base


def test_returns_minus_one_when_project_dir_missing(tmp_path):
    item = _item(tmp_path, project_dir=str(tmp_path / "nonexistent"))
    assert codex_session.run(item) == -1


def test_returns_subprocess_exit_code(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result):
        assert codex_session.run(_item(tmp_path)) == 0


def test_fresh_command_uses_codex_exec_and_project_dir(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        codex_session.run(_item(tmp_path), codex_cmd="/usr/local/bin/codex")
    cmd = mock_run.call_args[0][0]
    assert cmd[0:2] == ["/usr/local/bin/codex", "exec"]
    assert "-C" in cmd
    assert str(tmp_path) in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "--dangerously-bypass-hook-trust" in cmd
    assert mock_run.call_args[1]["cwd"] == str(tmp_path)


def test_fresh_prompt_contains_title_description_and_loop_metadata(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        codex_session.run(_item(tmp_path))
    prompt = mock_run.call_args[0][0][2]
    assert "Fix auth bug" in prompt
    assert "Refactor auth.ts into two modules" in prompt
    assert "loop_item_id: 1" in prompt
    assert "loop_started_at:" in prompt


def test_resume_command_uses_codex_exec_resume(tmp_path):
    mock_result = MagicMock(returncode=0)
    item = _item(tmp_path, session_id="abc-123")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        codex_session.run(item)
    cmd = mock_run.call_args[0][0]
    assert cmd[0:4] == ["codex", "exec", "resume", "abc-123"]
    assert "-C" in cmd
    assert str(tmp_path) in cmd


def test_resume_prompt_contains_handoff_without_title_description(tmp_path):
    mock_result = MagicMock(returncode=0)
    item = _item(tmp_path, session_id="abc-123")
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        codex_session.run(item)
    prompt = mock_run.call_args[0][0][4]
    assert "AUTONOMOUS MODE" in prompt
    assert "writing-plans" in prompt
    assert "loop_item_id: 1" in prompt
    assert "Fix auth bug" not in prompt


def test_returns_minus_two_when_codex_cmd_not_found(tmp_path):
    with patch("subprocess.run", side_effect=FileNotFoundError("no such file")):
        assert codex_session.run(_item(tmp_path), codex_cmd="/nonexistent/codex") == -2
