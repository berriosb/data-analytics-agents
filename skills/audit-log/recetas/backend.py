"""
Backends de storage para el audit log: JSONL append-only (default) y
SQLite opcional (para queries).

Misma interface:
- write(event: dict) -> None
- query(filters: dict) -> list[dict]
- rotate_if_needed() -> None  (solo JSONL; SQLite no necesita)

El backend activo se elige via env var `AUDIT_LOG_BACKEND` (jsonl|sqlite).
Default: jsonl.
"""

from __future__ import annotations

import json
import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any


AUDIT_DIR = Path(os.environ.get(
    "AUDIT_LOG_DIR",
    Path.home() / ".agents" / "audit",
))
LOG_FILE = AUDIT_DIR / "events.jsonl"
SQLITE_FILE = AUDIT_DIR / "events.sqlite"
_MAX_SIZE_BYTES = 1_000_000  # 1 MB
_KEEP_FILES = 10


class Backend(ABC):
    @abstractmethod
    def write(self, event: dict[str, Any]) -> None: ...
    @abstractmethod
    def query(self, filters: dict[str, Any]) -> list[dict[str, Any]]: ...


class JsonlBackend(Backend):
    """JSONL append-only con rotacion automatica por tamano."""

    def write(self, event: dict[str, Any]) -> None:
        self._rotate_if_needed()
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line)

    def query(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        # Leer todos los archivos de rotacion (activo + .1 a .N)
        files = [LOG_FILE] + [
            AUDIT_DIR / f"events.jsonl.{i}" for i in range(1, _KEEP_FILES + 1)
        ]
        for f in files:
            if not f.exists():
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if _matches(event, filters):
                    results.append(event)
        return results

    def _rotate_if_needed(self) -> None:
        if not LOG_FILE.exists():
            return
        if LOG_FILE.stat().st_size < _MAX_SIZE_BYTES:
            return
        # Rotar .N a .N+1, etc., activo a .1
        oldest = AUDIT_DIR / f"events.jsonl.{_KEEP_FILES}"
        if oldest.exists():
            oldest.unlink()
        for i in range(_KEEP_FILES - 1, 0, -1):
            src = AUDIT_DIR / f"events.jsonl.{i}"
            dst = AUDIT_DIR / f"events.jsonl.{i + 1}"
            if src.exists():
                src.replace(dst)
        LOG_FILE.replace(AUDIT_DIR / "events.jsonl.1")
        LOG_FILE.touch()


class SqliteBackend(Backend):
    """SQLite indexado, util para queries con muchos filtros."""

    def __init__(self) -> None:
        self._ensure_table()

    def _ensure_table(self) -> None:
        SQLITE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(SQLITE_FILE) as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    actor TEXT,
                    action TEXT,
                    engine TEXT,
                    target TEXT,
                    status TEXT,
                    n_rows INTEGER,
                    duration_ms INTEGER,
                    sql_preview TEXT,
                    error TEXT,
                    redacted_fields TEXT
                )
            """)
            con.execute("CREATE INDEX IF NOT EXISTS idx_actor ON events(actor)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_action ON events(action)")
            con.execute("CREATE INDEX IF NOT EXISTS idx_ts ON events(timestamp)")

    def write(self, event: dict[str, Any]) -> None:
        with sqlite3.connect(SQLITE_FILE) as con:
            con.execute(
                """INSERT INTO events
                   (timestamp, actor, action, engine, target, status,
                    n_rows, duration_ms, sql_preview, error, redacted_fields)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.get("timestamp"),
                    event.get("actor"),
                    event.get("action"),
                    event.get("engine"),
                    event.get("target"),
                    event.get("status"),
                    event.get("n_rows"),
                    event.get("duration_ms"),
                    event.get("sql_preview"),
                    event.get("error"),
                    ",".join(event.get("redacted_fields", [])),
                ),
            )

    def query(self, filters: dict[str, Any]) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        for key, col in [
            ("actor", "actor"), ("action", "action"),
            ("engine", "engine"), ("status", "status"),
        ]:
            if filters.get(key):
                clauses.append(f"{col} = ?")
                params.append(filters[key])
        since = filters.get("since")
        until = filters.get("until")
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if until:
            clauses.append("timestamp <= ?")
            params.append(until)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = filters.get("limit", 100)
        sql = (f"SELECT timestamp, actor, action, engine, target, status, "
               f"n_rows, duration_ms, sql_preview, error, redacted_fields "
               f"FROM events{where} ORDER BY timestamp DESC LIMIT ?")
        params.append(limit)
        with sqlite3.connect(SQLITE_FILE) as con:
            rows = con.execute(sql, params).fetchall()
        return [_row_to_dict(r) for r in rows]


def _row_to_dict(row: tuple) -> dict[str, Any]:
    return {
        "timestamp": row[0], "actor": row[1], "action": row[2],
        "engine": row[3], "target": row[4], "status": row[5],
        "n_rows": row[6], "duration_ms": row[7], "sql_preview": row[8],
        "error": row[9],
        "redacted_fields": [f for f in (row[10] or "").split(",") if f],
    }


def _matches(event: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Filtros para JSONL: equality + since/until."""
    for key in ("actor", "action", "engine", "status"):
        if filters.get(key) and event.get(key) != filters[key]:
            return False
    since = filters.get("since")
    if since and event.get("timestamp", "") < since:
        return False
    until = filters.get("until")
    if until and event.get("timestamp", "") > until:
        return False
    return True


_active_backend: Backend | None = None


def get_backend() -> Backend:
    """Singleton lazy del backend activo."""
    global _active_backend
    if _active_backend is not None:
        return _active_backend
    backend_type = os.environ.get("AUDIT_LOG_BACKEND", "jsonl").lower()
    if backend_type == "sqlite":
        _active_backend = SqliteBackend()
    else:
        _active_backend = JsonlBackend()
    return _active_backend


def reset_backend() -> None:
    """Para tests: resetea el singleton."""
    global _active_backend
    _active_backend = None