import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import codex_brainstorm_session as cbs


def _item(project_dir):
    return {"id": "1", "title": "T", "description": "D", "project_dir": str(project_dir)}


def test_returns_none_when_project_dir_missing(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path / "nope")}
    assert cbs.run(item) is None


def test_returns_none_when_interactive_launch_creates_no_session(tmp_path):
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir()
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0
    with patch("subprocess.Popen", return_value=mock_proc):
        result = cbs.run(_item(tmp_path), _codex_dir=str(codex_dir))
    assert result is None


def test_returns_none_when_no_spec_written(tmp_path):
    codex_dir = tmp_path / "codex" / "proj"
    codex_dir.mkdir(parents=True)

    def launch(*args, **kwargs):
        (codex_dir / "session-1.jsonl").write_text("{}")
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, None, 0]
        return mock_proc

    with patch("subprocess.Popen", side_effect=launch), \
         patch("time.sleep"):
        result = cbs.run(_item(tmp_path), _codex_dir=str(tmp_path / "codex"))
    assert result is None


def test_returns_session_id_when_spec_committed(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    codex_dir = tmp_path / "codex" / "proj"
    codex_dir.mkdir(parents=True)
    call_count = [0]
    mock_proc = MagicMock()

    def launch(*args, **kwargs):
        (codex_dir / "session-abc.jsonl").write_text("{}")
        return mock_proc

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-13-spec.md").write_text("spec")
        return None if call_count[0] < 3 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.Popen", side_effect=launch), \
         patch("time.sleep"), \
         patch.object(cbs, "_spec_committed", return_value=True):
        result = cbs.run(_item(tmp_path), _codex_dir=str(tmp_path / "codex"))
    assert result == "session-abc"


def test_terminates_process_when_spec_detected(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    codex_dir = tmp_path / "codex" / "proj"
    codex_dir.mkdir(parents=True)
    call_count = [0]
    mock_proc = MagicMock()

    def launch(*args, **kwargs):
        (codex_dir / "session-abc.jsonl").write_text("{}")
        return mock_proc

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-13-spec.md").write_text("spec")
        return None

    mock_proc.poll.side_effect = poll

    with patch("subprocess.Popen", side_effect=launch), \
         patch("time.sleep"), \
         patch.object(cbs, "_spec_committed", return_value=True):
        cbs.run(_item(tmp_path), _codex_dir=str(tmp_path / "codex"))
    mock_proc.terminate.assert_called_once()


def test_launch_command_uses_codex_prompt_and_project_dir(tmp_path):
    codex_dir = tmp_path / "codex" / "proj"
    codex_dir.mkdir(parents=True)
    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0
    with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
        cbs.run(_item(tmp_path), codex_cmd="/usr/local/bin/codex", _codex_dir=str(tmp_path / "codex"))
    cmd = mock_popen.call_args[0][0]
    assert cmd[0] == "/usr/local/bin/codex"
    assert "T\n\nD" in cmd
    assert "-C" in cmd
    assert str(tmp_path) in cmd
