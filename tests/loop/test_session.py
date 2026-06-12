import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import session


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
    assert session.run(item) == -1


def test_returns_subprocess_exit_code(tmp_path):
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result):
        assert session.run(_item(tmp_path)) == 0


def test_prompt_contains_title_and_description(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    prompt = mock_run.call_args[0][0][2]
    assert "Fix auth bug" in prompt
    assert "Refactor auth.ts into two modules" in prompt


def test_prompt_contains_loop_metadata(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    prompt = mock_run.call_args[0][0][2]
    assert "loop_item_id: 1" in prompt
    assert "loop_started_at:" in prompt


def test_prompt_includes_human_input_when_present(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path, human_input="Use the new v2 API"))
    prompt = mock_run.call_args[0][0][2]
    assert "human_input: Use the new v2 API" in prompt


def test_prompt_omits_human_input_when_absent(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    prompt = mock_run.call_args[0][0][2]
    assert "human_input" not in prompt


def test_subprocess_cwd_is_project_dir(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path))
    assert mock_run.call_args[1]["cwd"] == str(tmp_path)


def test_subprocess_uses_custom_claude_cmd(tmp_path):
    mock_result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        session.run(_item(tmp_path), claude_cmd="/usr/local/bin/claude")
    assert mock_run.call_args[0][0][0] == "/usr/local/bin/claude"
