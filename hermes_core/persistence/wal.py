"""SQLite WAL pragma configurations and connection helpers for Hermes Core Persistence."""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Optional

logger = logging.getLogger("hermes_core.wal")

# 64 MiB limit prevents runaway WAL files during high-volume sessions
DEFAULT_WAL_SIZE_LIMIT_BYTES = 64 * 1024 * 1024
DEFAULT_BUSY_TIMEOUT_MS = 10000


def configure_connection(
    conn: sqlite3.Connection,
    wal_size_limit_bytes: int = DEFAULT_WAL_SIZE_LIMIT_BYTES,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    read_only: bool = False,
) -> None:
    """Configure SQLite connection with production-grade WAL pragmas and locks."""
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {busy_timeout_ms};")
    conn.execute("PRAGMA foreign_keys = ON;")

    if not read_only:
        # Enable WAL mode
        try:
            mode = conn.execute("PRAGMA journal_mode = WAL;").fetchone()
            if mode and mode[0].lower() != "wal":
                logger.warning(f"Failed to enable WAL mode, got mode: {mode[0]}")
        except sqlite3.OperationalError as exc:
            logger.warning(f"Error setting WAL mode: {exc}")

        # Set synchronous mode to NORMAL (safe in WAL mode, faster than FULL)
        conn.execute("PRAGMA synchronous = NORMAL;")
        # Cap journal size limit
        conn.execute(f"PRAGMA journal_size_limit = {wal_size_limit_bytes};")
        # Ensure temporary tables reside in memory
        conn.execute("PRAGMA temp_store = MEMORY;")


def checkpoint_wal(conn: sqlite3.Connection, mode: str = "PASSIVE") -> tuple[int, int, int]:
    """Execute WAL checkpoint. Mode: PASSIVE, FULL, RESTART, or TRUNCATE.
    
    Returns (busy_flag, log_pages, checkpointed_pages).
    """
    valid_modes = {"PASSIVE", "FULL", "RESTART", "TRUNCATE"}
    mode_upper = mode.upper()
    if mode_upper not in valid_modes:
        raise ValueError(f"Invalid checkpoint mode: {mode}. Must be one of {valid_modes}")

    res = conn.execute(f"PRAGMA wal_checkpoint({mode_upper});").fetchone()
    if res:
        return int(res[0]), int(res[1]), int(res[2])
    return 0, 0, 0
