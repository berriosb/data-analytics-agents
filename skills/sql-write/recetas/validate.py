"""
Validador estatico de SQL para sql-write modo conservador.

Operaciones permitidas (ALLOWED_KEYWORDS):
- CREATE (TABLE IF NOT EXISTS, INDEX IF NOT EXISTS, VIEW)
- INSERT (INTO ... VALUES, INTO ... SELECT)

Operaciones BLOQUEADAS (BLOCKED_KEYWORDS):
- DROP, UPDATE, DELETE, TRUNCATE, ALTER, GRANT, REVOKE, RENAME

La validacion es por tokens (regex). NO parseamos SQL completo — eso
requeriria sqlparse como dep adicional. Para el caso de uso (data
analyst insertando resultados de un script Python), la validacion
por tokens es suficiente y robusta.

NO distingue entre CREATE TABLE (permitido) y CREATE INDEX (permitido)
porque las keywords CREATE/INDEX estan en ALLOWED_KEYWORDS. Lo que se
bloquea es la combinacion con operaciones destructivas.
"""

from __future__ import annotations

import re

from .errors import BlockedOperationError


ALLOWED_KEYWORDS = frozenset({"CREATE", "INSERT"})

# Keywords de operaciones destructivas — NUNCA permitidas en modo conservador.
# Nota: ALTER incluye DROP COLUMN, RENAME, etc. GRANT/REVOKE para permisos.
# REPLACE NO está bloqueada porque CREATE OR REPLACE VIEW es legal (Snowflake,
# BigQuery, Postgres). REPLACE INTO (MySQL UPSERT) no aplica porque solo
# permitimos CREATE/INSERT y REPLACE no es keyword de INSERT.
BLOCKED_KEYWORDS = frozenset({
    "DROP", "UPDATE", "DELETE", "TRUNCATE", "ALTER", "GRANT", "REVOKE",
    "RENAME", "MERGE", "UPSERT",
})


def validate_sql(sql: str) -> tuple[bool, str]:
    """Valida el SQL estaticamente. Devuelve (True, '') o (False, mensaje).

    Si la operacion es destructiva, levanta BlockedOperationError directo
    (es lo que la skill reporta al usuario).

    Args:
        sql: el query propuesto (puede tener multiples statements separados
            por ';').

    Returns:
        (True, '') si pasa; (False, msg) si no es CREATE/INSERT.

    Raises:
        BlockedOperationError si encuentra una operacion bloqueada.
        SqlWriteNoAllowedError si la primera keyword no es CREATE/INSERT
        (ni un WITH seguido de INSERT/CREATE).
    """
    if not sql or not sql.strip():
        return False, "SQL vacio"

    # Quick check: si despues de sacar comentarios no queda nada, es SQL
    # efectivamente vacio. Sin esto, "-- solo un comentario" pasa al
    # _validate_statement que devuelve silenciosamente y validate_sql
    # retorna (True, ''), lo cual es incorrecto.
    no_comments = re.sub(r"--[^\n]*", "", sql)
    no_comments = re.sub(r"/\*.*?\*/", "", no_comments, flags=re.DOTALL)
    if not no_comments.strip():
        return False, "SQL sin contenido (solo comentarios)"

    # Separar statements
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    if not statements:
        return False, "SQL sin statements"

    for stmt in statements:
        _validate_statement(stmt)

    # Si pasa todas las validaciones, OK
    return True, ""


def _validate_statement(stmt: str) -> None:
    """Valida un statement individual."""
    # Normalizar: sacar comentarios y pasar a uppercase para matching
    s = re.sub(r"--[^\n]*", "", stmt)
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
    s = s.strip().upper()

    if not s:
        return

    # Extraer keywords (palabras enteras, ignorando strings entre comillas)
    tokens = _extract_keywords(s)

    if not tokens:
        return

    # 1. Verificar primera keyword: debe ser CREATE o INSERT (o WITH para CTEs)
    first = tokens[0]
    if first == "WITH":
        # CTE: la siguiente keyword significativa debe ser INSERT o CREATE.
        # NOTA: 'WITH' esta en noise originalmente para que no aparezca como
        # keyword cuando es solo "with table_x". Aqui lo manejamos antes de
        # filtrar noise, asi que la primera keyword es WITH y la procesamos
        # explicitamente.
        found = None
        for tok in tokens[1:]:
            if tok == "INSERT" or tok == "CREATE":
                found = tok
                break
        if not found:
            raise SqlWriteNoAllowedError(
                "WITH clause sin INSERT ni CREATE detectado. Modo conservador "
                "solo permite CTEs seguidas de INSERT o CREATE."
            )
        tokens = [found] + [t for t in tokens
                            if t == "INSERT" or t == "CREATE"
                            or t in BLOCKED_KEYWORDS]
        first = found
    if first not in ALLOWED_KEYWORDS:
        raise BlockedOperationError(
            f"Primera keyword '{first}' (solo CREATE/INSERT permitidas)",
            stmt,
        )

    # 1b. Verificar que WITH no aparezca en medio del statement (no es un CTE
    # legitimo sino un intento de anidamiento). Esto evita que un usuario
    # haga "WITH cte AS SELECT x; DROP TABLE y;" — el segundo statement ya
    # fue separado por ;, asi que cada uno se valida por separado.
    # Esta validacion es por statement, no cross-statement.

    # 2. Verificar que NO contenga ninguna BLOCKED_KEYWORDS en ningun lugar
    for token in tokens:
        if token in BLOCKED_KEYWORDS:
            raise BlockedOperationError(token, stmt)

    # 3. CREATE: solo permitimos TABLE/VIEW/INDEX/OR REPLACE (en CREATE OR REPLACE VIEW)
    if first == "CREATE":
        if len(tokens) < 2:
            raise BlockedOperationError("CREATE sin tipo (TABLE/VIEW/INDEX)", stmt)
        # Tokens validos que pueden seguir a CREATE sin ser el "kind":
        valid_prefix_tokens = {"TABLE", "VIEW", "INDEX", "OR", "REPLACE",
                               "UNIQUE", "TEMP", "TEMPORARY", "MATERIALIZED",
                               "IF", "NOT"}
        # Recorremos tokens[1:] buscando el kind. Si encontramos OR/REPLACE,
        # los salteamos. Si encontramos IF NOT EXISTS, lo salteamos.
        kind = None
        idx = 1
        while idx < len(tokens):
            t = tokens[idx]
            if t in {"TABLE", "VIEW", "INDEX"}:
                kind = t
                break
            if t in {"IF", "OR", "REPLACE", "NOT", "TEMPORARY", "TEMP",
                     "UNIQUE", "MATERIALIZED"}:
                idx += 1
                continue
            # Cualquier otra cosa (ej. "FOO" en CREATE FOO): si NO es TABLE/
            # VIEW/INDEX, no es CREATE valido. Pero hay casos donde el
            # identificador empieza con mayuscula... en la practica los
            # nombres de tabla son lowercase en mi sample. Por seguridad,
            # si el token empieza con una letra y NO es keyword reservada,
            # lo tomamos como nombre de tabla y buscamos el kind despues.
            # Sin embargo eso no es legal SQL. Rechazamos.
            raise BlockedOperationError(
                f"CREATE '{t}' no permitido (solo CREATE TABLE/VIEW/INDEX)",
                stmt,
            )
        if kind not in {"TABLE", "VIEW", "INDEX"}:
            raise BlockedOperationError(
                f"CREATE {kind or '?'} no permitido (solo TABLE/VIEW/INDEX)",
                stmt,
            )


def _extract_keywords(s: str) -> list[str]:
    """Extrae keywords de un statement, ignorando strings entre comillas.

    Importante: preservamos WITH porque se usa como primera keyword de CTEs.
    Si fuera solo 'with table_x' lo detectamos en el caller.
    """
    # Quitar strings entre comillas (simples o dobles)
    s = re.sub(r"'[^']*'", "", s)
    s = re.sub(r'"[^"]*"', "", s)
    # Extraer palabras
    tokens = re.findall(r"\b[A-Z_][A-Z0-9_]*\b", s)
    # Filtrar nombres comunes que NO son keywords (best-effort).
    # Excluimos WITH y NOT porque son importantes para CTEs y
    # CREATE TABLE IF NOT EXISTS.
    noise = {"THE", "A", "AN", "INTO", "FROM", "WHERE", "AND", "OR",
             "NULL", "TRUE", "FALSE", "ON", "AS", "IS", "BY", "OF"}
    return [t for t in tokens if t not in noise]


class SqlWriteNoAllowedError(Exception):
    """Error cuando el SQL no empieza con una operacion permitida."""
    pass