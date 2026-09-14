"""
Introspeccion de schema para cloud warehouses.

Estrategia:
- Snowflake/BigQuery/Redshift: reusan `INFORMATION_SCHEMA.COLUMNS`
  (disponible en los 3 warehouses) — query SQL estandar.
- SQLite: usa `sqlite_master` + `PRAGMA table_info(<tabla>)` porque
  SQLite NO tiene `INFORMATION_SCHEMA` por diseño.
- Output en el mismo formato JSON compatible con `schema-mapper`.

Por ahora introspeccion de 1 schema (el de las credenciales). Para
multi-schema, el usuario pasa `schema=` o itera manualmente.
"""

from __future__ import annotations

from typing import Any

try:
    from sqlalchemy.engine import Engine
except ImportError:
    Engine = Any  # type: ignore


_INTROSPECT_QUERY_CLOUD = """
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_schema = :schema
ORDER BY table_name, ordinal_position
"""

_INTROSPECT_QUERY_SQLITE = """
SELECT name FROM sqlite_master WHERE type='table' ORDER BY name
"""


def introspect_schema(engine: Engine, schema: str | None = None) -> dict[str, Any]:
    """Introspecciona todas las tablas del schema activo y devuelve dict.

    Returns:
        {
            "warehouse": str,        # dialecto detectado
            "schema": str,           # nombre del schema
            "tables": {
                "<table_name>": {
                    "columns": [
                        {"name": str, "type": str, "nullable": bool}
                    ]
                }
            }
        }
    """
    name = engine.dialect.name.lower()
    if "sqlite" in name:
        return _introspect_sqlite(engine)
    return _introspect_cloud(engine, schema)


def _introspect_cloud(engine: Engine, schema: str | None) -> dict[str, Any]:
    schema = schema or _detect_default_schema(engine)
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(
            _INTROSPECT_QUERY_CLOUD, {"schema": schema}
        ).fetchall()

    tables: dict[str, list[dict[str, Any]]] = {}
    for table_name, col_name, data_type, is_nullable in rows:
        tables.setdefault(table_name, []).append({
            "name": col_name,
            "type": data_type,
            "nullable": is_nullable.upper() in ("YES", "TRUE", "T"),
        })
    return {
        "warehouse": engine.dialect.name,
        "schema": schema,
        "tables": tables,
    }


def _introspect_sqlite(engine: Engine) -> dict[str, Any]:
    """Introspeccion especifica para SQLite (usa sqlite_master + PRAGMA)."""
    with engine.connect() as conn:
        tables_rows = conn.exec_driver_sql(_INTROSPECT_QUERY_SQLITE).fetchall()
    tables: dict[str, list[dict[str, Any]]] = {}
    with engine.connect() as conn:
        for (table_name,) in tables_rows:
            col_rows = conn.exec_driver_sql(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
            cols = []
            for cid, name, ctype, notnull, default, pk in col_rows:
                cols.append({
                    "name": name,
                    "type": ctype or "UNKNOWN",
                    "nullable": not bool(notnull),
                })
            tables[table_name] = cols
    return {
        "warehouse": engine.dialect.name,
        "schema": "main",
        "tables": tables,
    }


def _detect_default_schema(engine: Engine) -> str:
    """Lee el schema por default del engine segun el dialecto."""
    name = engine.dialect.name.lower()
    if name.startswith("snowflake"):
        return "PUBLIC"
    if name.startswith("bigquery"):
        raise ValueError(
            "BigQuery requiere pasar schema='project.dataset_name' "
            "explicitamente. Ej: introspect_schema(engine, 'mydataset')"
        )
    if "redshift" in name or "postgres" in name:
        return "public"
    return "public"