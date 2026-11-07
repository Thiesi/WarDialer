"""The local disk hygiene guards (tests/scratch_guard.py, scripts/clean_scratch.py)."""
import os
import time

from scripts import clean_scratch
from tests import scratch_guard as guard


def _files(folder, count):
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (folder / f"f{i}").write_text("x")


def test_basetemp_outside_the_worktree_or_the_fixed_name_is_allowed(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    assert guard.basetemp_problem(None, root) is None
    assert guard.basetemp_problem(tmp_path / "elsewhere", root) is None
    assert guard.basetemp_problem(root / ".test-tmp" / "pytest", root) is None


def test_a_fresh_basetemp_inside_the_worktree_is_refused(tmp_path):
    problem = guard.basetemp_problem(tmp_path / "build" / "pytest-issue7", tmp_path)
    assert problem and ".test-tmp/pytest" in problem


def test_scratch_over_the_limit_is_refused_and_names_the_cleanup(tmp_path):
    _files(tmp_path / ".test-tmp" / "a", 3)
    _files(tmp_path / "build" / "pytest-x", 3)
    assert guard.scratch_problem(tmp_path, limit=6) is None
    problem = guard.scratch_problem(tmp_path, limit=5)
    assert problem and "clean_scratch.py" in problem


def test_only_this_projects_temp_entries_count(tmp_path):
    _files(tmp_path / "wardialer-gallery-run-abc", 4)
    _files(tmp_path / "someone-else", 50)
    assert guard.temp_files(tmp_path) == 4
    assert guard.temp_problem(tmp_path, limit=4) is None
    assert "--temp" in guard.temp_problem(tmp_path, limit=3)


def test_clean_removes_scratch_and_keeps_owner_files(tmp_path):
    for name in (".test-tmp/pytest", ".pytest_cache/v", "build/pytest-old", "tools/__pycache__"):
        _files(tmp_path / name, 2)
    _files(tmp_path / "build" / "gallery", 2)
    _files(tmp_path / ".venv" / "__pycache__", 2)
    (tmp_path / "keep.py").write_text("x")
    assert clean_scratch.clean(tmp_path) == 0
    for gone in (".test-tmp", ".pytest_cache", "build/pytest-old", "tools/__pycache__"):
        assert not (tmp_path / gone).exists(), gone
    assert (tmp_path / "build" / "gallery" / "f0").exists()
    assert (tmp_path / ".venv" / "__pycache__" / "f0").exists()
    assert (tmp_path / "keep.py").exists()


def test_clean_temp_keeps_recent_entries_and_ignores_other_projects(tmp_path):
    old, new, other = (tmp_path / n for n in ("wardialer-old", "wardialer-new", "other-old"))
    for folder in (old, new, other):
        _files(folder, 1)
    stale = time.time() - 48 * 3600
    for path in (old / "f0", old, other / "f0", other):
        os.utime(path, (stale, stale))
    assert clean_scratch.clean_temp(tmp_path) == 0
    assert not old.exists()
    assert new.exists() and other.exists()


def test_clean_unlinks_a_symlink_without_touching_its_target(tmp_path):
    target = tmp_path / "precious"
    _files(target, 1)
    link = tmp_path / "wardialer-link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        import pytest
        pytest.skip("symlinks need developer mode on Windows")
    assert clean_scratch.remove(link) == []
    assert not link.exists() and (target / "f0").exists()
