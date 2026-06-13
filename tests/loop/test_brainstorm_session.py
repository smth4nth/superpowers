import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import brainstorm_session as bs


def _item(project_dir):
    return {"id": "1", "title": "T", "project_dir": str(project_dir)}


def test_returns_none_when_project_dir_missing(tmp_path):
    item = {"id": "1", "title": "T", "project_dir": str(tmp_path / "nope")}
    assert bs.run(item) is None


def test_returns_none_when_no_spec_written(tmp_path):
    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, None, 0]
    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"):
        result = bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))
    assert result is None


def test_returns_none_when_spec_written_but_no_session_file(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()

    mock_proc = MagicMock()
    call_count = [0]

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-12-spec-design.md").write_text("spec")
        return None if call_count[0] < 3 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"), \
         patch.object(bs, "_spec_committed", return_value=True):
        result = bs.run(_item(tmp_path), _claude_dir=str(claude_dir))
    assert result is None


def test_returns_session_id_when_spec_and_session_found(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "my-project"
    claude_dir.mkdir(parents=True)

    mock_proc = MagicMock()
    call_count = [0]

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-12-spec-design.md").write_text("spec")
            (claude_dir / "my-session-id.jsonl").write_text("{}")
        return None if call_count[0] < 3 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"), \
         patch.object(bs, "_spec_committed", return_value=True):
        result = bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))
    assert result == "my-session-id"


def test_terminates_process_when_spec_detected(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "proj"
    claude_dir.mkdir(parents=True)

    mock_proc = MagicMock()
    call_count = [0]

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-12-spec-design.md").write_text("spec")
            (claude_dir / "sess.jsonl").write_text("{}")
        return None if call_count[0] < 4 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"), \
         patch.object(bs, "_spec_committed", return_value=True):
        bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))

    mock_proc.terminate.assert_called_once()


def test_returns_session_id_when_user_exits_naturally_with_spec(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "proj"
    claude_dir.mkdir(parents=True)
    (specs_dir / "2026-06-12-spec-design.md").write_text("spec")
    (claude_dir / "natural-exit-session.jsonl").write_text("{}")

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0  # already exited

    with patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"):
        result = bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))
    assert result == "natural-exit-session"


def test_spec_committed_returns_true_on_clean_status(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert bs._spec_committed(str(tmp_path), tmp_path / "spec.md") is True


def test_spec_committed_returns_false_on_dirty_status(tmp_path):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="?? spec.md\n")
        assert bs._spec_committed(str(tmp_path), tmp_path / "spec.md") is False


def test_spec_committed_returns_false_on_os_error(tmp_path):
    with patch("subprocess.run", side_effect=OSError("no git")):
        assert bs._spec_committed(str(tmp_path), tmp_path / "spec.md") is False
