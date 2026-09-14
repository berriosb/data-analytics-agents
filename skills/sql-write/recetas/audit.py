"""
Audit log append-only JSON para sql-write.

Cada escritura exitosa o fallida se registra en
`~/.agents/audit/sql-write.log` con:
- timestamp (ISO 8601 UTC)
- action ('insert', 'create+insert', 'dry-run', 'rejected')
- engine (sqlite, snowflake, bigquery, redshift)
- target (table_name o ruta)
- n_rows (si aplica)
- duration_ms
- status ('ok' | 'failed' | 'rejected')
- error (si fallo)
- sql_preview (primeros 200 chars del query)

Append-only: nunca borra entries. Rotacion: archivo nuevo cuando el
activo supera 1MB (max ~10 archivos historicos).
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_AUDIT_DIR = Path(os.environ.get("SQL_WRITE_AUDIT_DIR",
                                  Path.home() / ".agents" / "audit"))
_LOG_FILE = _AUDIT_DIR / "sql-write.log"
_MAX_SIZE_BYTES = 1_000_000  # 1 MB
_KEEP_FILES = 10


def get_audit_path() -> Path:
    """Devuelve el path al archivo de audit log actual."""
    return _LOG_FILE


def audit_log(action: str, engine: str, target: str, status: str,
              n_rows: int | None = None, duration_ms: int | None = None,
              sql_preview: str | None = None,
              error: str | None = None) -> None:
    """Escribe una entrada al audit log.

    Args:
        action: 'insert' | 'create+insert' | 'dry-run' | 'rejected'
        engine: 'sqlite' | 'snowflake' | 'bigquery' | 'redshift'
        target: tabla destino o ruta
        status: 'ok' | 'failed' | 'rejected'
        n_rows: filas afectadas (None si no aplica)
        duration_ms: duracion en ms (None si no se midio)
        sql_preview: primeros 200 chars del SQL ejecutado
        error: mensaje de error si fallo
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "engine": engine,
        "target": target,
        "status": status,
        "n_rows": n_rows,
        "duration_ms": duration_ms,
        "sql_preview": sql_preview,
        "error": error,
    }
    # Filtrar keys con None para JSON mas limpio
    entry = {k: v for k, v in entry.items() if v is not None}

    _rotate_if_needed()
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with _LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _rotate_if_needed() -> None:
    """Si el archivo activo supera MAX_SIZE, rotar."""
    if not _LOG_FILE.exists():
        return
    if _LOG_FILE.stat().st_size < _MAX_SIZE_BYTES:
        return
    # Rotar: sql-write.log -> sql-write.log.1 (el mas viejo se borra)
    oldest = _AUDIT_DIR / f"sql-write.log.{_KEEP_FILES}"
    if oldest.exists():
        oldest.unlink()
    for i in range(_KEEP_FILES - 1, 0, -1):
        src = _AUDIT_DIR / f"sql-write.log.{i}"
        dst = _AUDIT_DIR / f"sql-write.log.{i + 1}"
        if src.exists():
            shutil.move(str(src), str(dst))
    shutil.move(str(_LOG_FILE), str(_AUDIT_DIR / "sql-write.log.1"))
    _LOG_FILE.touch()