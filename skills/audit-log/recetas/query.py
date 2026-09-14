"""
API de lectura: `query_audit(...)` con filtros.

Filtros soportados (todos opcionales):
- actor: nombre exacto del agente o usuario
- action: 'select' | 'insert' | 'create' | 'dry-run' | 'rejected'
- engine: 'sqlite' | 'postgres' | 'snowflake' | etc.
- status: 'ok' | 'failed' | 'rejected'
- since: timestamp ISO 8601 (inclusivo)
- until: timestamp ISO 8601 (inclusivo)
- limit: maximo de eventos a devolver (default 100)

Devuelve lista de eventos ordenados por timestamp descendente.
"""

from __future__ import annotations

from typing import Any

from .backend import get_backend


def query_audit(actor: str | None = None, action: str | None = None,
                engine: str | None = None, status: str | None = None,
                since: str | None = None, until: str | None = None,
                limit: int = 100) -> list[dict[str, Any]]:
    """Query sobre el audit log con filtros combinables."""
    filters = {k: v for k, v in {
        "actor": actor, "action": action, "engine": engine,
        "status": status, "since": since, "until": until, "limit": limit,
    }.items() if v is not None}
    return get_backend().query(filters)