"""Minimal stdlib-only XLSX reader for pinned static Dataset B."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

COL_REF_RE = re.compile(r"^([A-Z]+)")


def _col_to_index(ref: str) -> int:
    """Convert an Excel cell reference like 'AB12' to a 0-based column index."""
    match = COL_REF_RE.match(ref)
    if not match:
        raise ValueError(f"Invalid Excel cell reference: {ref!r}")
    idx = 0
    for ch in match.group(1):
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


def _local_tag(tag: str) -> str:
    """Strip XML namespace prefix."""
    return tag.rsplit("}", 1)[-1]


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    """Parse xl/sharedStrings.xml if present in the XLSX archive."""
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for si in root:
        if _local_tag(si.tag) != "si":
            continue
        parts = [
            elem.text for elem in si.iter() if _local_tag(elem.tag) == "t" and elem.text is not None
        ]
        strings.append("".join(parts))
    return strings


def _find_first_sheet_path(zf: zipfile.ZipFile) -> str:
    """Resolve the first worksheet XML path from workbook.xml and its rels."""
    wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
    first_rid: str | None = None
    for elem in wb_root.iter():
        if _local_tag(elem.tag) == "sheet":
            for k, v in elem.attrib.items():
                if k == "r:id" or k.endswith("}id"):
                    first_rid = v
                    break
            if first_rid is not None:
                break

    if first_rid is not None and "xl/_rels/workbook.xml.rels" in zf.namelist():
        rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel in rels_root:
            if rel.attrib.get("Id") == first_rid:
                target = rel.attrib["Target"].lstrip("/")
                if not target.startswith("xl/"):
                    target = f"xl/{target}"
                return target

    return "xl/worksheets/sheet1.xml"


def read_xlsx_rows(xlsx_path: Path) -> list[list[str]]:
    """Read all rows from the first sheet of an XLSX file using only stdlib."""
    with zipfile.ZipFile(xlsx_path, "r") as zf:
        shared_strings = _load_shared_strings(zf)
        sheet_path = _find_first_sheet_path(zf)
        root = ET.fromstring(zf.read(sheet_path))

    rows: list[list[str]] = []
    max_cols = 0

    for elem in root.iter():
        if _local_tag(elem.tag) != "row":
            continue
        row_dict: dict[int, str] = {}
        for cell in elem:
            if _local_tag(cell.tag) != "c":
                continue
            ref = cell.attrib.get("r", "")
            col_idx = _col_to_index(ref) if ref else (max(row_dict.keys(), default=-1) + 1)
            cell_type = cell.attrib.get("t", "")

            val = ""
            if cell_type == "s":
                v_elem = next((ch for ch in cell if _local_tag(ch.tag) == "v"), None)
                if v_elem is not None and v_elem.text is not None:
                    val = shared_strings[int(v_elem.text)]
            elif cell_type == "inlineStr":
                parts = [
                    sub.text
                    for sub in cell.iter()
                    if _local_tag(sub.tag) == "t" and sub.text is not None
                ]
                val = "".join(parts)
            else:
                v_elem = next((ch for ch in cell if _local_tag(ch.tag) == "v"), None)
                if v_elem is not None and v_elem.text is not None:
                    val = v_elem.text

            row_dict[col_idx] = val
            if col_idx + 1 > max_cols:
                max_cols = col_idx + 1

        if row_dict:
            rows.append([row_dict.get(i, "") for i in range(max_cols)])

    return [row + [""] * (max_cols - len(row)) for row in rows]
