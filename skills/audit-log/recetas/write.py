"""
API de alto nivel: `audit_log(event)` y `audit_event(...)` helper.

Aplica redaction automatica de PII antes de escribir al backend.

Cualquier skill que toque DB (sql-analyst, sql-cloud-warehouse, sql-write)
DEBE importar `audit_log` de aca y registrar cada operacion:
- SELECT: action='select', status='ok'/'failed'
- INSERT/CREATE: action='insert'/'create', n_rows=...
- DROP/UPDATE/DELETE: action='rejected' (en sql-write modo conservador)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from .backend import get_backend
from .redact import redact_pii


@dataclass
class AuditEvent:
    actor: str                                          # agente o user
    action: str                                         # select|insert|create|dry-run|rejected
    engine: str                                         # sqlite|postgres|...
    target: str                                         # tabla o ruta
    status: str = "ok"                                  # ok|failed|rejected
    n_rows: int | None = None
    duration_ms: int | None = None
    sql_preview: str | None = None
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    redacted_fields: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Filtrar None para JSON limpio
        return {k: v for k, v in d.items() if v is not None and v != []}


def audit_event(actor: str, action: str, engine: str, target: str,
                status: str = "ok", n_rows: int | None = None,
                duration_ms: int | None = None,
                sql_preview: str | None = None,
                error: str | None = None) -> AuditEvent:
    """Helper para construir un AuditEvent con defaults razonables."""
    return AuditEvent(
        actor=actor,
        action=action,
        engine=engine,
        target=target,
        status=status,
        n_rows=n_rows,
        duration_ms=duration_ms,
        sql_preview=sql_preview,
        error=error,
    )


def audit_log(event: AuditEvent | dict[str, Any]) -> None:
    """Escribe un evento al backend activo, aplicando redaction.

    Acepta AuditEvent o dict (compatibilidad con sql-write que ya
    usaba el nombre `audit_log`).

    Redaction:
    - sql_preview: se redacta PII antes de guardar
    - error: idem
    - redacted_fields se popula con los nombres de los campos redacted
    """
    if isinstance(event, AuditEvent):
        e = event
    else:
        # Compat: dict con keys tipo 'action', 'engine', 'target', etc.
        e = AuditEvent(
            actor=event.get("actor", "unknown"),
            action=event.get("action", "unknown"),
            engine=event.get("engine", "unknown"),
            target=event.get("target", ""),
            status=event.get("status", "ok"),
            n_rows=event.get("n_rows"),
            duration_ms=event.get("duration_ms"),
            sql_preview=event.get("sql_preview"),
            error=event.get("error"),
            timestamp=event.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )

    # Redact PII en sql_preview y error
    redacted: list[str] = []
    if e.sql_preview:
        e.sql_preview, fields = redact_pii(e.sql_preview)
        redacted.extend(fields)
    if e.error:
        e.error, fields = redact_pii(e.error)
        redacted.extend(fields)
    e.redacted_fields = sorted(set(redacted))

    # Override actor desde env si esta (util para multi-user)
    if "AUDIT_LOG_ACTOR" in os.environ:
        e.actor = os.environ["AUDIT_LOG_ACTOR"]

    get_backend().write(e.to_dict())