"""Bronze-layer provenance and immutable storage helpers."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
REPO_DATA_DIR = REPO_ROOT / "data"


def get_git_provenance(repo_root: Path | None = None) -> tuple[str | None, bool | None]:
    """Return (git_commit_sha, git_dirty) for the given repository root."""
    cwd = repo_root or REPO_ROOT
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return commit, bool(status)
    except Exception:
        return None, None


def ensure_not_in_repo_data(target_dir: Path, repo_data_dir: Path | None = None) -> None:
    """Refuse writing offline/synthetic outputs into the tracked repository data/ directory."""
    data_root = (repo_data_dir or REPO_DATA_DIR).resolve()
    resolved = target_dir.resolve()
    if resolved == data_root or data_root in resolved.parents:
        raise ValueError(
            f"Refusing to write offline/synthetic output inside tracked data directory: {resolved}"
        )


def write_immutable_with_sidecar(
    raw_bytes: bytes,
    target_path: Path,
    sidecar_metadata: dict[str, Any],
) -> tuple[Path, Path]:
    """Write raw bytes unmodified and a JSON provenance sidecar, refusing overwrites.

    Args:
        raw_bytes: Unmodified raw payload bytes.
        target_path: Destination path for the raw payload.
        sidecar_metadata: Provenance metadata dictionary (sha256, git_commit, git_dirty added).

    Returns:
        Tuple of (raw_file_path, sidecar_json_path).

    Raises:
        FileExistsError: If either target_path or its sidecar already exists.
    """
    sidecar_path = (
        target_path.with_name(f"{target_path.stem}.sidecar.json")
        if target_path.suffix == ".json"
        else target_path.with_suffix(".json")
    )
    if target_path.exists():
        raise FileExistsError(f"Refusing to overwrite immutable bronze file: {target_path}")
    if sidecar_path.exists():
        raise FileExistsError(f"Refusing to overwrite immutable bronze sidecar: {sidecar_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    if "git_commit" in sidecar_metadata and "git_dirty" in sidecar_metadata:
        git_commit = sidecar_metadata["git_commit"]
        git_dirty = sidecar_metadata["git_dirty"]
    else:
        git_commit, git_dirty = get_git_provenance()

    full_sidecar = {
        **sidecar_metadata,
        "sha256": sha256_hex,
        "size_bytes": len(raw_bytes),
        "git_commit": git_commit,
        "git_dirty": git_dirty,
    }

    target_path.write_bytes(raw_bytes)
    sidecar_path.write_text(
        json.dumps(full_sidecar, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return target_path, sidecar_path
