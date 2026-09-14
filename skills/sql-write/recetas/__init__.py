"""
Recetas pre-aprobadas para escribir resultados de analisis a una DB de
manera segura (modo conservador: solo INSERT + CREATE TABLE IF NOT EXISTS).

Modulos:
- validate: valida SQL estaticamente contra la lista de operaciones
  bloqueadas (DROP/UPDATE/DELETE/TRUNCATE/ALTER/GRANT/REVOKE)
- connect: wrapper sobre SQLAlchemy + connect_warehouse de sql-cloud-warehouse
  con soporte para SQLite local
- execute: CREATE TABLE + INSERT con transaccion SQLAlchemy
- audit: log append-only JSON de todas las escrituras (quien-cuando-que)
- errors: excepciones consistentes

Modo conservador: NUNCA permite DROP/UPDATE/DELETE/TRUNCATE/ALTER.
Para esos, queda como ADR-003 (modo full con rollback scripts).
"""

from .validate import validate_sql, ALLOWED_KEYWORDS, BLOCKED_KEYWORDS
from .connect import connect_target
from .execute import dry_run, execute_insert
from .audit import audit_log, get_audit_path
from .errors import SqlWriteError, BlockedOperationError

__all__ = [
    "validate_sql",
    "ALLOWED_KEYWORDS",
    "BLOCKED_KEYWORDS",
    "connect_target",
    "dry_run",
    "execute_insert",
    "audit_log",
    "get_audit_path",
    "SqlWriteError",
    "BlockedOperationError",
]