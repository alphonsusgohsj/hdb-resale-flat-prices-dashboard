"""One place that opens the DuckDB connection.

Centralising this means every module talks to the *same* warehouse file and the
data directory is guaranteed to exist before we connect.
"""
from __future__ import annotations

import duckdb

import config


def connect() -> duckdb.DuckDBPyConnection:
    """Open (creating if needed) the warehouse DuckDB file."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(config.DB_PATH))
