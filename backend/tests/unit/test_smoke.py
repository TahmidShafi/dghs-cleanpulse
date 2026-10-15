"""Smoke tests verifying workspace dependencies and cleanpulse package integrity."""

import duckdb
import fastapi
import pandas as pd
import pandera.pandas as pa

import cleanpulse


def test_package_metadata() -> None:
    """Verify package version is defined."""
    assert cleanpulse.__version__ == "0.1.0"


def test_core_dependencies() -> None:
    """Verify core analytical and schema dependencies can be imported and initialized."""
    assert pa is not None
    assert duckdb is not None
    assert fastapi is not None
    assert pd is not None

    # Verify basic in-memory DuckDB query
    conn = duckdb.connect(database=":memory:")
    result = conn.execute("SELECT 1 AS num").fetchall()
    assert result == [(1,)]
    conn.close()
