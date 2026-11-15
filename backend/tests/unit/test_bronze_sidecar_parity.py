"""Read-only check that every tracked Bronze data file has exactly one sidecar."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BRONZE_ROOT = REPO_ROOT / "data" / "bronze"


def test_every_bronze_file_has_exactly_one_sidecar() -> None:
    if not BRONZE_ROOT.exists():
        return

    all_files = [p for p in BRONZE_ROOT.rglob("*") if p.is_file() and p.name != ".gitkeep"]
    sidecars = {p for p in all_files if p.name.endswith(".sidecar.json")}
    data_files = [p for p in all_files if p not in sidecars]

    matched_sidecars: set[Path] = set()
    for data_file in data_files:
        expected = (
            data_file.with_name(f"{data_file.stem}.sidecar.json")
            if data_file.suffix == ".json"
            else data_file.with_name(f"{data_file.name}.sidecar.json")
        )
        assert expected in sidecars, f"Missing sidecar {expected} for {data_file}"
        assert expected not in matched_sidecars, f"Duplicate sidecar mapping {expected}"
        matched_sidecars.add(expected)

    assert matched_sidecars == sidecars, (
        f"Orphan sidecars in data/bronze/: {sorted(sidecars - matched_sidecars)}"
    )
