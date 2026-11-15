"""Unit tests for Bronze provenance git_dirty filtering."""

from __future__ import annotations

import subprocess
from pathlib import Path

from cleanpulse.bronze.provenance import get_git_provenance


def _init_git_repo(repo_dir: Path) -> str:
    """Create a clean temporary git repository with one tracked file and return HEAD sha."""
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    tracked = repo_dir / "README.md"
    tracked.write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        text=True,
    ).strip()


def test_git_provenance_ignores_pipeline_output_paths(tmp_path: Path) -> None:
    """Untracked files under data/ or frontend/public/data/ must not mark git_dirty=True."""
    head_sha = _init_git_repo(tmp_path)

    (tmp_path / "data" / "bronze").mkdir(parents=True)
    (tmp_path / "data" / "bronze" / "raw.json").write_text("{}", encoding="utf-8")
    (tmp_path / "frontend" / "public" / "data").mkdir(parents=True)
    (tmp_path / "frontend" / "public" / "data" / "fallback_snapshot.json").write_text(
        "{}", encoding="utf-8"
    )

    commit, dirty = get_git_provenance(repo_root=tmp_path)
    assert commit == head_sha
    assert dirty is False


def test_git_provenance_marks_dirty_for_tracked_file_outside_data(tmp_path: Path) -> None:
    """Modifying a tracked file outside pipeline output paths must mark git_dirty=True."""
    head_sha = _init_git_repo(tmp_path)

    (tmp_path / "README.md").write_text("# modified\n", encoding="utf-8")

    commit, dirty = get_git_provenance(repo_root=tmp_path)
    assert commit == head_sha
    assert dirty is True
