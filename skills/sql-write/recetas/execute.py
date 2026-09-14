"""
Ejecucion segura de INSERT/CREATE TABLE con guardrails.

Flujo:
1. dry_run: genera el DDL + muestra preview sin tocar la DB
2. execute_insert: transaccion SQLAlchemy con rollback en error

Modos:
- "create": solo CREATE TABLE IF NOT EXISTS (la tabla debe existir ya o
  falla)
- "insert": INSERT INTO tabla existente (la tabla debe existir)
- "create-or-replace": CREATE TABLE (sin IF NOT EXISTS) si existe, falla
- "create-if-not-exists-else-insert": CREATE TABLE IF NOT EXISTS + INSERT
  (default, recomendado para resultados de analisis)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd
try:
    from sqlalchemy.engine import Engine
except ImportError:
    Engine = Any  # type: ignore

from .audit import audit_log
from .errors import SqlWriteError


def dry_run(engine: Engine, df: pd.DataFrame, table_name: str,
            schema: str | None = None,
            if_exists: str = "create-if-not-exists-else-insert") -> dict[str, Any]:
    """Genera preview de lo que va a pasar SIN ejecutar el INSERT.

    Returns:
        {
            "ddl": str,                  # CREATE TABLE statement
            "preview_rows": [dict],      # primeras 5 filas del DataFrame
            "n_rows": int,
            "columns": [(name, sql_type), ...],
            "table_exists": bool,
            "engine_name": str,
        }
    """
    if df.empty:
        raise SqlWriteError("DataFrame vacio, no hay nada para escribir.")
    if not table_name or not table_name.replace("_", "").isalnum():
        raise SqlWriteError(
            f"Nombre de tabla invalido: '{table_name}'. "
            "Solo letras, numeros y underscore."
        )

    engine_name = engine.dialect.name
    columns = _infer_columns(df, engine_name)
    ddl = _build_ddl(table_name, columns, schema, if_exists)
    table_exists = _check_table_exists(engine, table_name, schema)

    preview = df.head(5).to_dict(orient="records")

    return {
        "ddl": ddl,
        "preview_rows": preview,
        "n_rows": len(df),
        "columns": columns,
        "table_exists": table_exists,
        "engine_name": engine_name,
    }


def execute_insert(engine: Engine, df: pd.DataFrame, table_name: str,
                   schema: str | None = None,
                   if_exists: str = "create-if-not-exists-else-insert",
                   auto_confirm: bool = False) -> dict[str, Any]:
    """Ejecuta el INSERT (y CREATE si corresponde) en una transaccion.

    Args:
        engine: SQLAlchemy Engine.
        df: DataFrame a escribir.
        table_name: nombre de la tabla destino.
        schema: schema opcional (no usado en SQLite).
        if_exists: 'create' | 'insert' | 'create-if-not-exists-else-insert'.
        auto_confirm: si True, no pide confirmacion interactiva (usado en
            tests; en CLI/agent siempre False y el caller pide confirmacion).

    Returns:
        {"n_rows": int, "duration_ms": int, "table_name": str, "action": str}

    Raises:
        SqlWriteError si la ejecucion falla (rollback automatico).
    """
    info = dry_run(engine, df, table_name, schema, if_exists)
    engine_name = info["engine_name"]
    start = time.time()

    if not auto_confirm:
        raise SqlWriteError(
            "execute_insert requiere auto_confirm=True para ejecutar. "
            "El caller (skill o agente) DEBE pedir confirmacion al usuario "
            "antes de llamar con auto_confirm=True."
        )

    try:
        with engine.begin() as conn:
            # Primero ejecuto el DDL (CREATE TABLE IF NOT EXISTS) si el modo
            # lo requiere. Este paso es idempotente: si la tabla existe, no
            # hace nada.
            if if_exists in {"create", "create-if-not-exists-else-insert"}:
                conn.exec_driver_sql(info["ddl"])
                # CREATE + INSERT en una sola operacion atomica.
                # pandas to_sql hace CREATE si no existe; como la tabla
                # YA existe (gracias al DDL), le decimos 'append'.
                df.to_sql(
                    table_name,
                    con=conn,
                    schema=schema,
                    if_exists="append",
                    index=False,
                    chunksize=1000,
                )
                action = ("create+insert"
                          if if_exists == "create-if-not-exists-else-insert"
                          else "create")
            else:
                # Modo insert puro: tabla debe existir. Si no, falla.
                df.to_sql(
                    table_name,
                    con=conn,
                    schema=schema,
                    if_exists="append",
                    index=False,
                    chunksize=1000,
                )
                action = "insert"
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        audit_log(
            action=action,
            engine=engine_name,
            target=f"{schema}.{table_name}" if schema else table_name,
            status="failed",
            duration_ms=duration_ms,
            error=str(e),
        )
        raise SqlWriteError(
            f"INSERT fallo (rollback automatico): {e}"
        ) from e

    duration_ms = int((time.time() - start) * 1000)
    audit_log(
        action=action,
        engine=engine_name,
        target=f"{schema}.{table_name}" if schema else table_name,
        status="ok",
        n_rows=len(df),
        duration_ms=duration_ms,
    )

    return {
        "n_rows": len(df),
        "duration_ms": duration_ms,
        "table_name": table_name,
        "action": action,
    }


def _infer_columns(df: pd.DataFrame, engine_name: str) -> list[tuple[str, str]]:
    """Mapea los dtypes de pandas a tipos SQL del engine."""
    type_map = {
        "sqlite": {
            "int64": "INTEGER", "int32": "INTEGER", "float64": "REAL",
            "float32": "REAL", "bool": "BOOLEAN", "datetime64[ns]": "TIMESTAMP",
            "object": "TEXT",
        },
        "postgresql": {
            "int64": "BIGINT", "int32": "INTEGER", "float64": "DOUBLE PRECISION",
            "float32": "REAL", "bool": "BOOLEAN", "datetime64[ns]": "TIMESTAMP",
            "object": "TEXT",
        },
        "mysql": {
            "int64": "BIGINT", "int32": "INT", "float64": "DOUBLE",
            "float32": "FLOAT", "bool": "TINYINT", "datetime64[ns]": "DATETIME",
            "object": "TEXT",
        },
        "snowflake": {
            "int64": "NUMBER(38,0)", "int32": "NUMBER(38,0)",
            "float64": "FLOAT", "float32": "FLOAT",
            "bool": "BOOLEAN", "datetime64[ns]": "TIMESTAMP_NTZ",
            "object": "TEXT",
        },
        "bigquery": {
            "int64": "INT64", "int32": "INT64", "float64": "FLOAT64",
            "float32": "FLOAT64", "bool": "BOOL", "datetime64[ns]": "TIMESTAMP",
            "object": "STRING",
        },
    }
    family = engine_name.lower()
    mapping = type_map.get(family, type_map["sqlite"])

    cols: list[tuple[str, str]] = []
    for col_name, dtype in df.dtypes.items():
        sql_type = mapping.get(str(dtype), "TEXT")
        cols.append((col_name, sql_type))
    return cols


def _build_ddl(table_name: str, columns: list[tuple[str, str]],
               schema: str | None, if_exists: str) -> str:
    """Construye el CREATE TABLE statement."""
    full_name = f"{schema}.{table_name}" if schema else table_name
    col_defs = ", ".join(f'"{c}" {t}' for c, t in columns)
    if if_exists in {"create", "create-if-not-exists-else-insert"}:
        return f"CREATE TABLE IF NOT EXISTS {full_name} ({col_defs})"
    return ""


def _check_table_exists(engine: Engine, table_name: str,
                        schema: str | None) -> bool:
    """Chequea si la tabla existe (heuristica via information_schema)."""
    engine_name = engine.dialect.name.lower()
    if "sqlite" in engine_name:
        # SQLite usa sqlite_master
        with engine.connect() as conn:
            rows = conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchall()
            return len(rows) > 0
    # Otros: INFORMATION_SCHEMA (puede no existir en todos los engines)
    try:
        with engine.connect() as conn:
            sql = ("SELECT 1 FROM information_schema.tables WHERE table_name = ?"
                   if not schema
                   else "SELECT 1 FROM information_schema.tables WHERE table_schema = ? AND table_name = ?")
            params = (table_name,) if not schema else (schema, table_name)
            rows = conn.exec_driver_sql(sql, params).fetchall()
            return len(rows) > 0
    except Exception:
        # Si no podemos chequear, asumimos que NO existe (modo conservador)
        return False