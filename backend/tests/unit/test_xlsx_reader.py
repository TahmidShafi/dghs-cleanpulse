"""Unit tests for the stdlib-only XLSX reader."""

from __future__ import annotations

import zipfile
from pathlib import Path

from cleanpulse.bronze.xlsx_reader import read_xlsx_rows


def _build_minimal_xlsx(path: Path) -> None:
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
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<si><t>Division</t></si>"
        "<si><t>Year</t></si>"
        "<si><t>Month</t></si>"
        "<si><t>Infected</t></si>"
        "<si><t>Dhaka </t></si>"
        "<si><t>January</t></si>"
        "<si><t>February</t></si>"
        "</sst>"
    )
    # Row 2 has merged-style populated Division ('Dhaka ') and Year (2020).
    # Row 3 omits A and B (sparse empty cells representing merged cells).
    # Row 4 uses inlineStr for Division.
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        '<row r="1">'
        '<c r="A1" t="s"><v>0</v></c>'
        '<c r="B1" t="s"><v>1</v></c>'
        '<c r="C1" t="s"><v>2</v></c>'
        '<c r="D1" t="s"><v>3</v></c>'
        "</row>"
        '<row r="2">'
        '<c r="A2" t="s"><v>4</v></c>'
        '<c r="B2"><v>2020</v></c>'
        '<c r="C2" t="s"><v>5</v></c>'
        '<c r="D2"><v>88</v></c>'
        "</row>"
        '<row r="3">'
        '<c r="C3" t="s"><v>6</v></c>'
        '<c r="D3"><v>17</v></c>'
        "</row>"
        '<row r="4">'
        '<c r="A4" t="inlineStr"><is><t>Barishal</t></is></c>'
        '<c r="B4"><v>2021</v></c>'
        '<c r="C4" t="s"><v>5</v></c>'
        '<c r="D4"><v>12</v></c>'
        "</row>"
        "</sheetData>"
        "</worksheet>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("xl/workbook.xml", workbook_xml)
        zf.writestr("xl/_rels/workbook.xml.rels", rels_xml)
        zf.writestr("xl/sharedStrings.xml", shared_xml)
        zf.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def test_read_xlsx_rows_handles_sparse_merged_cells_and_trailing_space(
    tmp_path: Path,
) -> None:
    xlsx_path = tmp_path / "sample.xlsx"
    _build_minimal_xlsx(xlsx_path)

    rows = read_xlsx_rows(xlsx_path)
    assert rows == [
        ["Division", "Year", "Month", "Infected"],
        ["Dhaka ", "2020", "January", "88"],
        ["", "", "February", "17"],
        ["Barishal", "2021", "January", "12"],
    ]
