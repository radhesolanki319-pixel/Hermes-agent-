"""Database schema definitions and DDL migrations for Hermes Core Persistence."""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

CORE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS system_prompts (
    hash TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT,
    system_prompt_hash TEXT,
    parent_session_id TEXT,
    started_at REAL NOT NULL,
    ended_at REAL,
    end_reason TEXT,
    message_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    reasoning_tokens INTEGER DEFAULT 0,
    metadata_json TEXT DEFAULT '{}',
    FOREIGN KEY (parent_session_id) REFERENCES sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (system_prompt_hash) REFERENCES system_prompts(hash)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT,
    tool_call_id TEXT,
    tool_calls TEXT,
    tool_name TEXT,
    timestamp REAL NOT NULL,
    token_count INTEGER DEFAULT 0,
    reasoning TEXT,
    metadata_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_sessions_parent ON sessions(parent_session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at DESC);
"""

FTS5_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_messages USING fts5(
    content,
    role,
    tool_name,
    content='messages',
    content_rowid='id',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS trg_messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO fts_messages(rowid, content, role, tool_name)
    VALUES (new.id, new.content, new.role, new.tool_name);
END;

CREATE TRIGGER IF NOT EXISTS trg_messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO fts_messages(fts_messages, rowid, content, role, tool_name)
    VALUES ('delete', old.id, old.content, old.role, old.tool_name);
END;

CREATE TRIGGER IF NOT EXISTS trg_messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO fts_messages(fts_messages, rowid, content, role, tool_name)
    VALUES ('delete', old.id, old.content, old.role, old.tool_name);
    INSERT INTO fts_messages(rowid, content, role, tool_name)
    VALUES (new.id, new.content, new.role, new.tool_name);
END;
"""

# Fallback FTS5 if trigram tokenizer is not present (standard unicode61)
FTS5_UNICODE_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS fts_messages USING fts5(
    content,
    role,
    tool_name,
    content='messages',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS trg_messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO fts_messages(rowid, content, role, tool_name)
    VALUES (new.id, new.content, new.role, new.tool_name);
END;

CREATE TRIGGER IF NOT EXISTS trg_messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO fts_messages(fts_messages, rowid, content, role, tool_name)
    VALUES ('delete', old.id, old.content, old.role, old.tool_name);
END;

CREATE TRIGGER IF NOT EXISTS trg_messages_au AFTER UPDATE ON messages BEGIN
    INSERT INTO fts_messages(fts_messages, rowid, content, role, tool_name)
    VALUES ('delete', old.id, old.content, old.role, old.tool_name);
    INSERT INTO fts_messages(rowid, content, role, tool_name)
    VALUES (new.id, new.content, new.role, new.tool_name);
END;
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize core tables, indexes, and full-text search triggers."""
    with conn:
        conn.executescript(CORE_SCHEMA_SQL)
        # Check and record version
        row = conn.execute("SELECT version FROM schema_version LIMIT 1;").fetchone()
        if not row:
            conn.execute("INSERT INTO schema_version (version) VALUES (?);", (SCHEMA_VERSION,))

        # Try initializing FTS5 with trigram, fall back to unicode61 if needed
        try:
            conn.executescript(FTS5_SCHEMA_SQL)
        except sqlite3.OperationalError:
            conn.executescript(FTS5_UNICODE_SCHEMA_SQL)
