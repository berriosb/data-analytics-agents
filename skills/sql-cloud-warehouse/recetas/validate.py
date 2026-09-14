"""
Validacion y dry-run de queries en cloud warehouses.

- `validate_query`: valida sintaxis basica (parentesis balanceados, comillas)
  sin tocar la DB. Util para feedback rapido antes de gastar credits.
- `explain_query`: pide EXPLAIN/dry-run al warehouse cuando lo soporta.
  - Snowflake:  EXPLAIN (FORMAT JSON) <query>
  - BigQuery:   Job con dryRun=True (via cliente bigquery)
  - Redshift:   EXPLAIN <query>

Si el warehouse no soporta EXPLAIN, devuelve None y no falla.
"""

from __future__ import annotations

from typing import Any

try:
    from sqlalchemy.engine import Engine
except ImportError:
    Engine = Any  # type: ignore

from .dialect_snippets import dialect_for


def validate_query(query: str) -> tuple[bool, str]:
    """Validacion estatica basica: parentesis balanceados, comillas.

    Returns:
        (True, '') si pasa; (False, mensaje) si falla.
    """
    if not query or not query.strip():
        return False, "Query vacia."
    parens = 0
    in_str: str | None = None
    for i, ch in enumerate(query):
        if in_str:
            if ch == in_str:
                # Chequear que no sea un escape doble
                if i > 0 and query[i - 1] == "\\":
                    continue
                in_str = None
            continue
        if ch in ("'", '"', "`"):
            in_str = ch
            continue
        if ch == "(":
            parens += 1
        elif ch == ")":
            parens -= 1
            if parens < 0:
                return False, f"Parentesis de cierre sin apertura en pos {i}."
    if parens != 0:
        return False, f"Parentesis desbalanceados: {parens} abiertos sin cerrar."
    if in_str is not None:
        return False, f"Comilla {in_str} sin cerrar."
    return True, ""


def explain_query(engine: Engine, query: str) -> dict[str, Any] | None:
    """Ejecuta EXPLAIN en el warehouse. Devuelve el plan o None si no soporta.

    BigQuery usa dryRun=True via cliente nativo (no via SQLAlchemy); aqui
    implementamos el caso Snowflake/Redshift que es por SQL.
    """
    wh = dialect_for(engine.dialect.name.lower())
    if wh == "redshift":
        explain_sql = f"EXPLAIN {query}"
    elif wh == "snowflake":
        explain_sql = f"EXPLAIN USING TABULAR {query}"
    else:
        # BigQuery no soporta EXPLAIN via SQL, requiere cliente nativo
        return None
    try:
        with engine.connect() as conn:
            rows = conn.exec_driver_sql(explain_sql).fetchall()
        return {"warehouse": wh, "plan_rows": [list(r) for r in rows]}
    except Exception as e:
        return {"warehouse": wh, "error": str(e)}