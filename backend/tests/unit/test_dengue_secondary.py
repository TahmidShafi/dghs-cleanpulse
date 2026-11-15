"""Unit tests for Silver secondary dengue builders (Dataset A daily & Dataset B monthly)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

from cleanpulse.silver.dengue_secondary import (
    DATASET_A_FILE_SPECS,
    SECONDARY_SOURCE_LABEL,
    build_dengue_division_daily,
    build_dengue_division_monthly_b,
    write_or_merge_audit_anomalies,
)


def _write_synthetic_dataset_a(bronze_a_dir: Path) -> None:
    bronze_a_dir.mkdir(parents=True, exist_ok=True)
    for idx, (filename, (case_col, _raw, _canon)) in enumerate(DATASET_A_FILE_SPECS.items()):
        df = pd.DataFrame(
            {
                "Date": ["01-01-22", "02-01-22"],
                case_col: [idx + 1, idx + 2],
                "Rainfall": [99.9, 88.8],  # Must be dropped
            }
        )
        df.to_csv(bronze_a_dir / filename, index=False)


def _build_synthetic_dataset_b_xlsx(xlsx_path: Path) -> None:
    xlsx_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        '<row r="1">'
        '<c r="A1" t="inlineStr"><is><t>Division</t></is></c>'
        '<c r="B1" t="inlineStr"><is><t>Year</t></is></c>'
        '<c r="C1" t="inlineStr"><is><t>Month</t></is></c>'
        '<c r="D1" t="inlineStr"><is><t>Infected</t></is></c>'
        '<c r="E1" t="inlineStr"><is><t>Death</t></is></c>'
        "</row>"
        '<row r="2">'
        '<c r="A2" t="inlineStr"><is><t>Dhaka </t></is></c>'
        '<c r="B2"><v>2022</v></c>'
        '<c r="C2" t="inlineStr"><is><t>January</t></is></c>'
        '<c r="D2"><v>60</v></c>'
        '<c r="E2"><v>0</v></c>'
        "</row>"
        '<row r="3">'
        '<c r="C3" t="inlineStr"><is><t>February</t></is></c>'
        '<c r="D3"><v>10</v></c>'
        '<c r="E3"><v>0</v></c>'
        "</row>"
        "</sheetData>"
        "</worksheet>"
    )
    with zipfile.ZipFile(xlsx_path, "w") as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def test_build_dengue_division_daily_drops_weather_and_logs_normalizations(
    tmp_path: Path,
) -> None:
    bronze_a = tmp_path / "bronze_a"
    silver_dir = tmp_path / "silver"
    _write_synthetic_dataset_a(bronze_a)

    out_path, anomalies = build_dengue_division_daily(bronze_a, silver_dir)
    df = pd.read_parquet(out_path)

    assert len(df) == 16
    assert list(df.columns) == ["report_date", "division", "cases", "source_label"]
    assert (df["source_label"] == SECONDARY_SOURCE_LABEL).all()
    assert "Chattogram" in set(df["division"])
    # chittagong, khulna, Rajhshahi, Syllhet -> 4 normalized labels
    assert len(anomalies) == 4
    assert all(a["severity"] == "INFO" for a in anomalies)
    assert all("REPAIRED" in a["explanation"] for a in anomalies)


def test_build_dengue_division_monthly_b_handles_merged_cells_and_dhaka_space(
    tmp_path: Path,
) -> None:
    bronze_b = tmp_path / "bronze_b"
    silver_dir = tmp_path / "silver"
    _build_synthetic_dataset_b_xlsx(bronze_b / "dataset.xlsx")

    out_path, anomalies = build_dengue_division_monthly_b(bronze_b, silver_dir)
    df = pd.read_parquet(out_path)

    assert len(df) == 2
    assert list(df["division"]) == ["Dhaka", "Dhaka"]
    assert list(df["month"]) == [1, 2]
    assert list(df["infected"]) == [60, 10]

    audit_path = write_or_merge_audit_anomalies(anomalies, silver_dir)
    audit_df = pd.read_parquet(audit_path)
    assert len(audit_df) == 3  # Dhaka trailing space + Division ffill + Year ffill
    assert set(audit_df["severity"]) == {"INFO"}
