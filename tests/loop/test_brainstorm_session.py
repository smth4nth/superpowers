import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "loop"))
import brainstorm_session as bs


def _item(project_dir):
    return {"id": "1", "title": "T", "description": "D", "project_dir": str(project_dir)}


def test_returns_none_when_project_dir_missing(tmp_path):
    item = {"id": "1", "title": "T", "description": "D", "project_dir": str(tmp_path / "nope")}
    assert bs.run(item) is None


def test_returns_none_when_seed_creates_no_session(tmp_path):
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    with patch("subprocess.run", return_value=MagicMock(returncode=0)), \
         patch("subprocess.Popen"):
        result = bs.run(_item(tmp_path), _claude_dir=str(claude_dir))
    assert result is None


def test_returns_none_when_no_spec_written(tmp_path):
    claude_dir = tmp_path / "claude" / "proj"
    claude_dir.mkdir(parents=True)

    def seed(*args, **kwargs):
        (claude_dir / "seed-session.jsonl").write_text("{}")
        return MagicMock(returncode=0)

    mock_proc = MagicMock()
    mock_proc.poll.side_effect = [None, None, 0]

    with patch("subprocess.run", side_effect=seed), \
         patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"):
        result = bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))
    assert result is None


def test_returns_session_id_when_spec_committed(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "proj"
    claude_dir.mkdir(parents=True)

    call_count = [0]

    def seed(*args, **kwargs):
        (claude_dir / "seed-session.jsonl").write_text("{}")
        return MagicMock(returncode=0)

    mock_proc = MagicMock()

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-12-spec.md").write_text("spec")
        return None if call_count[0] < 3 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.run", side_effect=seed), \
         patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"), \
         patch.object(bs, "_spec_committed", return_value=True):
        result = bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))
    assert result == "seed-session"


def test_terminates_process_when_spec_detected(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "proj"
    claude_dir.mkdir(parents=True)

    call_count = [0]

    def seed(*args, **kwargs):
        (claude_dir / "sess.jsonl").write_text("{}")
        return MagicMock(returncode=0)

    mock_proc = MagicMock()

    def poll():
        call_count[0] += 1
        if call_count[0] == 2:
            (specs_dir / "2026-06-12-spec.md").write_text("spec")
        return None if call_count[0] < 4 else 0

    mock_proc.poll.side_effect = poll

    with patch("subprocess.run", side_effect=seed), \
         patch("subprocess.Popen", return_value=mock_proc), \
         patch("time.sleep"), \
         patch.object(bs, "_spec_committed", return_value=True):
        bs.run(_item(tmp_path), _claude_dir=str(tmp_path / "claude"))

    mock_proc.terminate.assert_called_once()


def test_returns_session_id_when_user_exits_naturally_with_spec(tmp_path):
    specs_dir = tmp_path / "docs" / "superpowers" / "specs"
    specs_dir.mkdir(parents=True)
    claude_dir = tmp_path / "claude" / "proj"
    claude_dir.mkdir(parents=True)
    (specs_dir / "2026-06-12-spec.md").write_text("spec")

    def seed(*args, **kwargs):
        (claude_dir / "natural-exit-session.jsonl").write_text("{}")
        return MagicMock(returncode=0)

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 0  # already exited

    with patch("subprocess.run", side_effect=seed), \
         patch("subprocess.Popen", return_value=mock_proc), \
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
