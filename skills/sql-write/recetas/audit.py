"""
Audit log append-only JSON para sql-write.

El audit log es TRANSVERSAL al toolkit: `sql-write` escribe al mismo
archivo que la skill `audit-log` (`~/.agents/audit/events.jsonl`),
para que un `cat events.jsonl | jq` vea entradas uniformes de todas
las skills que tocan DB (sql-write, sql-cloud-warehouse, sql-analyst).

Cada escritura exitosa o fallida se registra en
`~/.agents/audit/events.jsonl` (override por env var `AUDIT_LOG_DIR`)
con:
- timestamp (ISO 8601 UTC)
- actor (None para sql-write; la skill no identifica usuario todavia)
- action ('insert', 'create+insert', 'dry-run', 'rejected')
- engine (sqlite, snowflake, bigquery, redshift)
- target (table_name o ruta)
- n_rows (si aplica)
- duration_ms
- status ('ok' | 'failed' | 'rejected')
- error (si fallo)
- sql_preview (primeros 200 chars del query)

Append-only: nunca borra entries. Rotacion: archivo nuevo cuando el
activo supera 1MB (max ~10 archivos historicos: `events.jsonl.1` a
`events.jsonl.10`).

Nota historica: hasta v1.1.0 sql-write escribia a `sql-write.log` con
env var `SQL_WRITE_AUDIT_DIR`. Esas dos claves ya no funcionan — el
codigo ahora usa solo `events.jsonl` + `AUDIT_LOG_DIR`. Si un deploy
viejo dependia del path anterior, hay que migrar manualmente cualquier
herramienta downstream que lea `sql-write.log`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_AUDIT_DIR = Path(os.environ.get("AUDIT_LOG_DIR",
                                  Path.home() / ".agents" / "audit"))
_LOG_FILE = _AUDIT_DIR / "events.jsonl"
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
        "actor": None,  # sql-write no identifica usuario; uniformidad con audit-log
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
    # Rotar: events.jsonl -> events.jsonl.1 (el mas viejo se borra)
    oldest = _AUDIT_DIR / f"events.jsonl.{_KEEP_FILES}"
    if oldest.exists():
        oldest.unlink()
    for i in range(_KEEP_FILES - 1, 0, -1):
        src = _AUDIT_DIR / f"events.jsonl.{i}"
        dst = _AUDIT_DIR / f"events.jsonl.{i + 1}"
        if src.exists():
            src.replace(dst)
    _LOG_FILE.replace(_AUDIT_DIR / "events.jsonl.1")
    _LOG_FILE.touch()