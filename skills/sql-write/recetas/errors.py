"""
Errores consistentes con mensajes accionables para sql-write.
"""


class SqlWriteError(Exception):
    """Error general de sql-write (DB no accesible, transaccion fallo, etc)."""


class BlockedOperationError(SqlWriteError):
    """El SQL propuesto contiene una operacion destructiva bloqueada en modo conservador."""

    def __init__(self, operation: str, sql: str):
        msg = (
            f"Operacion '{operation}' BLOQUEADA en modo conservador. "
            "sql-write v1 solo permite CREATE TABLE IF NOT EXISTS e INSERT. "
            "Para DROP/UPDATE/DELETE/TRUNCATE/ALTER, usar el modo full (ADR-003). "
            f"SQL propuesto: {sql[:100]!r}"
        )
        super().__init__(msg)
        self.operation = operation
        self.sql = sql