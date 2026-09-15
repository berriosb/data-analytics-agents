"""
Unit tests para `skills/sql-write/recetas/validate.py`.

`validate_sql` es el guardrail central de sql-write modo conservador:
rechaza DROP/UPDATE/DELETE/TRUNCATE/ALTER/GRANT/REVOKE antes de cualquier
ejecucion. Es la pieza mas critica de seguridad de la skill — un bug
aca podria causar perdida de datos en produccion.

Cobertura:
- ALLOWED: CREATE TABLE/VIEW/INDEX, INSERT, CTEs
- BLOCKED: todas las operaciones destructivas
- Edge cases: SQL vacio, comentarios, strings entre comillas, mayusculas/minusculas
"""

from __future__ import annotations

import pytest

from sql_write import recetas as sw
from sql_write.recetas.errors import BlockedOperationError
from sql_write.recetas.validate import SqlWriteNoAllowedError

# Cualquier operacion no permitida dispara BlockedOperationError o
# SqlWriteNoAllowedError (segun como arranca el statement). Para los tests
# de bloqueo lo que importa es que la query NO se valide, asi que aceptamos
# cualquiera de las dos.
BlockedLike = (BlockedOperationError, SqlWriteNoAllowedError)


# -----------------------------------------------------------------------
# Happy path — operaciones permitidas
# -----------------------------------------------------------------------

class TestAllowedOperations:
    """El modo conservador debe aceptar CREATE TABLE IF NOT EXISTS e INSERT."""

    @pytest.mark.parametrize("sql", [
        "CREATE TABLE foo (id INT)",
        "CREATE TABLE IF NOT EXISTS foo (id INT, name VARCHAR(50))",
        "CREATE TABLE foo (id BIGINT PRIMARY KEY, created_at TIMESTAMP)",
        "CREATE VIEW bar AS SELECT id FROM foo",
        "CREATE INDEX idx_foo_id ON foo (id)",
        "CREATE UNIQUE INDEX idx_foo_email ON foo (email)",
        "CREATE OR REPLACE VIEW bar AS SELECT * FROM foo",
    ])
    def test_create_statements_pass(self, sql: str) -> None:
        ok, msg = sw.validate_sql(sql)
        assert ok is True, f"Deberia aceptar '{sql}', rechazo: {msg!r}"
        assert msg == ""

    @pytest.mark.parametrize("sql", [
        "INSERT INTO foo (id, name) VALUES (1, 'a')",
        "INSERT INTO foo SELECT id, name FROM bar",
        "INSERT INTO foo VALUES (1), (2), (3)",
    ])
    def test_insert_statements_pass(self, sql: str) -> None:
        ok, _ = sw.validate_sql(sql)
        assert ok is True

    def test_cte_followed_by_insert_passes(self) -> None:
        """WITH cte AS (...) INSERT INTO target SELECT * FROM cte — caso comun."""
        sql = (
            "WITH recent AS (SELECT id FROM foo WHERE date > '2026-01-01') "
            "INSERT INTO archive SELECT * FROM recent"
        )
        ok, msg = sw.validate_sql(sql)
        assert ok is True, f"CTE+INSERT deberia pasar, rechazo: {msg!r}"

    def test_multiple_statements_separated_by_semicolon(self) -> None:
        """Varios statements validos en el mismo string se validan por separado."""
        sql = (
            "CREATE TABLE a (id INT); "
            "INSERT INTO a VALUES (1); "
            "INSERT INTO a VALUES (2)"
        )
        ok, _ = sw.validate_sql(sql)
        assert ok is True


# -----------------------------------------------------------------------
# Operaciones bloqueadas — el corazon del guardrail
# -----------------------------------------------------------------------

class TestBlockedOperations:
    """Ninguna operacion destructiva debe pasar el modo conservador."""

    @pytest.mark.parametrize("sql", [
        "DROP TABLE foo",
        "DROP TABLE IF EXISTS foo",
        "DROP DATABASE bar",
        "DROP SCHEMA bar",
        "UPDATE foo SET x = 1 WHERE id = 1",
        "UPDATE foo SET x = 1",
        "DELETE FROM foo",
        "DELETE FROM foo WHERE id = 1",
        "TRUNCATE TABLE foo",
        "TRUNCATE foo",
        "ALTER TABLE foo ADD COLUMN x INT",
        "ALTER TABLE foo DROP COLUMN x",
        "ALTER TABLE foo RENAME TO bar",
        "GRANT SELECT ON foo TO user_bob",
        "REVOKE SELECT ON foo FROM user_bob",
        "RENAME TABLE foo TO bar",
        "MERGE INTO foo USING bar ON foo.id = bar.id",
        "UPSERT INTO foo VALUES (1)",
    ])
    def test_destructive_operations_blocked(self, sql: str) -> None:
        with pytest.raises(BlockedOperationError):
            sw.validate_sql(sql)

    def test_cte_followed_by_drop_blocked(self) -> None:
        """WITH cte AS (...) DROP TABLE target — el DROP debe detectarse.

        En la practica, validate_sql detecta el WITH sin INSERT/CREATE
        antes que el DROP y dispara SqlWriteNoAllowedError. Lo importante
        es que la query NO pase — el DROP queda efectivamente bloqueado.
        """
        sql = "WITH cte AS (SELECT id FROM foo) DROP TABLE target"
        with pytest.raises(BlockedLike):
            sw.validate_sql(sql)


# -----------------------------------------------------------------------
# Edge cases de robustez
# -----------------------------------------------------------------------

class TestEdgeCases:
    """Casos limite que la validacion debe manejar sin romperse."""

    def test_empty_sql_returns_false(self) -> None:
        ok, msg = sw.validate_sql("")
        assert ok is False
        assert "vacio" in msg.lower()

    def test_whitespace_only_returns_false(self) -> None:
        ok, msg = sw.validate_sql("   \n\t  ")
        assert ok is False

    def test_only_comments_returns_false(self) -> None:
        ok, msg = sw.validate_sql("-- solo un comentario\n/* otro */")
        assert ok is False
        assert "comentario" in msg.lower() or "vacio" in msg.lower()

    def test_string_with_blocked_keyword_passes(self) -> None:
        """Un string que contiene 'DROP' entre comillas no debe disparar el bloqueo."""
        sql = "INSERT INTO foo VALUES ('este texto dice DROP pero es string')"
        ok, _ = sw.validate_sql(sql)
        assert ok is True

    def test_lowercase_create_passes(self) -> None:
        """El validador es case-insensitive para keywords."""
        ok, _ = sw.validate_sql("create table foo (id int)")
        assert ok is True

    def test_blocked_keyword_lowercase_blocked(self) -> None:
        """El bloqueo tambien aplica en minusculas (uppercase se aplica internamente)."""
        with pytest.raises(BlockedOperationError):
            sw.validate_sql("drop table foo")

    def test_first_keyword_must_be_create_or_insert(self) -> None:
        """SELECT solo es lectura — no esta en modo conservador de escritura."""
        with pytest.raises(BlockedOperationError):
            sw.validate_sql("SELECT * FROM foo")

    def test_with_without_insert_or_create_blocked(self) -> None:
        """WITH ... SELECT no es valido en modo escritura (es lectura)."""
        sql = "WITH cte AS (SELECT * FROM foo) SELECT * FROM cte"
        with pytest.raises(SqlWriteNoAllowedError) as exc:
            sw.validate_sql(sql)
        assert "WITH" in str(exc.value) or "INSERT" in str(exc.value).upper()
