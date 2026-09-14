"""
Recetas pre-aprobadas para el audit log transversal del toolkit.

Modulos:
- redact: deteccion y reemplazo de PII (email, RUT CL, telefono, tarjeta)
  via regex configurables
- backend: dos implementaciones del log (JSONL append-only + SQLite opcional)
  con la misma interface (write, query, rotate_if_needed)
- init: crea el directorio y archivo/tabla inicial con permisos 0600
- write: API de alto nivel `audit_log(event)` que aplica redaction
  + escribe al backend activo
- query: API de lectura `query_audit(...)` con filtros

Cross-cutting:
- Cualquier skill que toque DB (sql-analyst, sql-cloud-warehouse, sql-write)
  DEBE importar `audit_log` de aca y registrar cada operacion.
"""

from .redact import redact_pii, set_extra_patterns, DEFAULT_PATTERNS
from .backend import (
    JsonlBackend, SqliteBackend, get_backend, AUDIT_DIR, LOG_FILE,
)
from .init import init_audit_log
from .write import audit_log, audit_event, AuditEvent
from .query import query_audit

__all__ = [
    "redact_pii",
    "set_extra_patterns",
    "DEFAULT_PATTERNS",
    "JsonlBackend",
    "SqliteBackend",
    "get_backend",
    "AUDIT_DIR",
    "LOG_FILE",
    "init_audit_log",
    "audit_log",
    "audit_event",
    "AuditEvent",
    "query_audit",
]