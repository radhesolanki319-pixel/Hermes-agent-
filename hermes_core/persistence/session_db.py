"""High-concurrency SQLite WAL Session Database with FTS5 search and session branching."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional
import uuid

from hermes_core.persistence.schema import init_schema
from hermes_core.persistence.wal import configure_connection, checkpoint_wal

logger = logging.getLogger("hermes_core.session_db")


class SessionDB:
    """Production-grade SQLite WAL state store for agent sessions and conversational memory."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)

        self._lock = threading.RLock()
        if self.db_path == ":memory:":
            self._write_conn = sqlite3.connect(":memory:", check_same_thread=False)
            configure_connection(self._write_conn)
            init_schema(self._write_conn)
            self._read_conn = self._write_conn
        else:
            self._write_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            configure_connection(self._write_conn)
            init_schema(self._write_conn)
            self._read_conn = sqlite3.connect(self.db_path, check_same_thread=False)
            configure_connection(self._read_conn, read_only=True)

    def _hash_system_prompt(self, prompt: str) -> str:
        return hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()

    def register_system_prompt(self, prompt: str) -> str:
        """Register a system prompt deduplicated by SHA-256 hash."""
        p_hash = self._hash_system_prompt(prompt)
        with self._lock, self._write_conn:
            self._write_conn.execute(
                """
                INSERT INTO system_prompts (hash, prompt, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(hash) DO NOTHING;
                """,
                (p_hash, prompt, time.time()),
            )
        return p_hash

    def create_session(
        self,
        session_id: Optional[str] = None,
        source: str = "cli",
        title: Optional[str] = None,
        system_prompt: Optional[str] = None,
        parent_session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new conversational session."""
        sid = session_id or str(uuid.uuid4())
        prompt_hash = self.register_system_prompt(system_prompt) if system_prompt else None
        now = time.time()
        meta_str = json.dumps(metadata or {})

        with self._lock, self._write_conn:
            self._write_conn.execute(
                """
                INSERT INTO sessions (
                    id, source, title, system_prompt_hash, parent_session_id,
                    started_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (sid, source, title or f"Session {sid[:8]}", prompt_hash, parent_session_id, now, meta_str),
            )
        return sid

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session metadata."""
        row = self._read_conn.execute(
            """
            SELECT s.*, sp.prompt as system_prompt
            FROM sessions s
            LEFT JOIN system_prompts sp ON s.system_prompt_hash = sp.hash
            WHERE s.id = ?;
            """,
            (session_id,),
        ).fetchone()

        if not row:
            return None
        data = dict(row)
        data["metadata"] = json.loads(data.get("metadata_json") or "{}")
        return data

    def list_sessions(self, limit: int = 50, source: Optional[str] = None) -> List[Dict[str, Any]]:
        """List recent sessions ordered by start time."""
        query = "SELECT * FROM sessions"
        params: list[Any] = []
        if source:
            query += " WHERE source = ?"
            params.append(source)
        query += " ORDER BY started_at DESC LIMIT ?;"
        params.append(limit)

        rows = self._read_conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
            result.append(d)
        return result

    def branch_session(
        self,
        parent_session_id: str,
        new_title: Optional[str] = None,
        source: Optional[str] = None,
        copy_history: bool = True,
    ) -> str:
        """Branch a session from an existing parent session."""
        parent = self.get_session(parent_session_id)
        if not parent:
            raise ValueError(f"Parent session {parent_session_id} not found.")

        new_sid = str(uuid.uuid4())
        branch_title = new_title or f"Branch of {parent.get('title') or parent_session_id[:8]}"
        branch_source = source or parent.get("source", "cli")

        meta = dict(parent.get("metadata", {}))
        meta["branched_from"] = parent_session_id
        meta["branch_timestamp"] = time.time()

        self.create_session(
            session_id=new_sid,
            source=branch_source,
            title=branch_title,
            parent_session_id=parent_session_id,
            metadata=meta,
        )

        if copy_history:
            messages = self.get_messages(parent_session_id)
            for msg in messages:
                self.add_message(
                    session_id=new_sid,
                    role=msg["role"],
                    content=msg.get("content"),
                    tool_call_id=msg.get("tool_call_id"),
                    tool_calls=msg.get("tool_calls"),
                    tool_name=msg.get("tool_name"),
                    reasoning=msg.get("reasoning"),
                    token_count=msg.get("token_count", 0),
                    metadata=msg.get("metadata"),
                )

        return new_sid

    def add_message(
        self,
        session_id: str,
        role: str,
        content: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_name: Optional[str] = None,
        reasoning: Optional[str] = None,
        token_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Add a message to the session transcript and update message counters."""
        tc_json = json.dumps(tool_calls) if tool_calls else None
        meta_json = json.dumps(metadata or {})
        now = time.time()

        with self._lock, self._write_conn:
            cursor = self._write_conn.execute(
                """
                INSERT INTO messages (
                    session_id, role, content, tool_call_id, tool_calls,
                    tool_name, timestamp, token_count, reasoning, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    session_id,
                    role,
                    content,
                    tool_call_id,
                    tc_json,
                    tool_name,
                    now,
                    token_count,
                    reasoning,
                    meta_json,
                ),
            )
            msg_id = cursor.lastrowid

            # Increment session counters
            tool_inc = 1 if (role == "tool" or tool_name or tool_calls) else 0
            self._write_conn.execute(
                """
                UPDATE sessions
                SET message_count = message_count + 1,
                    tool_call_count = tool_call_count + ?
                WHERE id = ?;
                """,
                (tool_inc, session_id),
            )

        return int(msg_id)

    def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve conversation messages for a session in chronological order."""
        query = "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC, id ASC"
        params: list[Any] = [session_id]
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = self._read_conn.execute(query, params).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tool_calls"] = json.loads(d["tool_calls"]) if d.get("tool_calls") else None
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
            result.append(d)
        return result

    def search_messages(
        self, query: str, session_id: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Perform full-text search across messages using FTS5 BM25 relevance ranking."""
        clean_query = query.strip().replace('"', '""')
        if not clean_query:
            return []

        fts_query = f'"{clean_query}"'
        sql = """
            SELECT m.*, bm25(fts_messages) as rank
            FROM fts_messages fts
            JOIN messages m ON fts.rowid = m.id
            WHERE fts_messages MATCH ?
        """
        params: list[Any] = [fts_query]

        if session_id:
            sql += " AND m.session_id = ?"
            params.append(session_id)

        sql += " ORDER BY rank ASC LIMIT ?;"
        params.append(limit)

        try:
            rows = self._read_conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            # Fallback to simple LIKE if MATCH syntax fails
            like_sql = """
                SELECT m.*, 0.0 as rank
                FROM messages m
                WHERE m.content LIKE ?
            """
            like_params: list[Any] = [f"%{clean_query}%"]
            if session_id:
                like_sql += " AND m.session_id = ?"
                like_params.append(session_id)
            like_sql += " ORDER BY m.timestamp DESC LIMIT ?;"
            like_params.append(limit)
            rows = self._read_conn.execute(like_sql, like_params).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["tool_calls"] = json.loads(d["tool_calls"]) if d.get("tool_calls") else None
            d["metadata"] = json.loads(d.get("metadata_json") or "{}")
            result.append(d)
        return result

    def record_usage(
        self,
        session_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
        reasoning_tokens: int = 0,
    ) -> None:
        """Record cumulative token metrics on session."""
        with self._lock, self._write_conn:
            self._write_conn.execute(
                """
                UPDATE sessions
                SET input_tokens = input_tokens + ?,
                    output_tokens = output_tokens + ?,
                    cache_read_tokens = cache_read_tokens + ?,
                    cache_write_tokens = cache_write_tokens + ?,
                    reasoning_tokens = reasoning_tokens + ?
                WHERE id = ?;
                """,
                (
                    input_tokens,
                    output_tokens,
                    cache_read_tokens,
                    cache_write_tokens,
                    reasoning_tokens,
                    session_id,
                ),
            )

    def end_session(self, session_id: str, reason: str = "completed") -> None:
        """Mark session ended with reason."""
        with self._lock, self._write_conn:
            self._write_conn.execute(
                "UPDATE sessions SET ended_at = ?, end_reason = ? WHERE id = ?;",
                (time.time(), reason, session_id),
            )

    def checkpoint(self, mode: str = "PASSIVE") -> tuple[int, int, int]:
        """Checkpoint SQLite WAL file."""
        with self._lock:
            return checkpoint_wal(self._write_conn, mode)

    def close(self) -> None:
        """Close reader and writer database connections safely."""
        with self._lock:
            try:
                self.checkpoint("TRUNCATE")
            except Exception:
                pass
            if self._read_conn and self._read_conn is not self._write_conn:
                self._read_conn.close()
            if self._write_conn:
                self._write_conn.close()

    def __enter__(self) -> SessionDB:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
