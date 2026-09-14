"""
Conexion a Snowflake, BigQuery o Redshift via SQLAlchemy + driver oficial.

Las deps cloud son OPCIONALES (peerDeps). Si no estan instaladas, la skill
emite MissingDependencyError con un comando pip install accionable.

Credenciales via os.environ (sin secrets hardcodeados):
- Snowflake:  SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
              SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, [SNOWFLAKE_SCHEMA]
- BigQuery:   GOOGLE_APPLICATION_CREDENTIALS (path al JSON service account)
              o WAREHOUSE_PROJECT, WAREHOUSE_DATASET
- Redshift:   REDSHIFT_HOST, REDSHIFT_PORT, REDSHIFT_USER, REDSHIFT_PASSWORD,
              REDSHIFT_DATABASE
"""

from __future__ import annotations

import os
from typing import Any

try:
    from sqlalchemy.engine import Engine
except ImportError:
    Engine = Any  # type: ignore

from .errors import MissingCredentialsError, MissingDependencyError


SUPPORTED = ("snowflake", "bigquery", "redshift")


def connect_warehouse(warehouse_type: str | None = None,
                       **overrides: Any) -> Engine:
    """Construye un SQLAlchemy Engine para el warehouse.

    Args:
        warehouse_type: 'snowflake' | 'bigquery' | 'redshift'. Si None,
            lee WAREHOUSE_TYPE de os.environ.
        **overrides: parametros especificos por warehouse (ej. account,
            database) que toman precedencia sobre env.

    Raises:
        MissingCredentialsError si faltan env vars
        MissingDependencyError si el driver no esta instalado
    """
    wh = (warehouse_type or os.environ.get("WAREHOUSE_TYPE", "")).lower()
    if wh not in SUPPORTED:
        raise ValueError(
            f"WAREHOUSE_TYPE debe ser uno de {SUPPORTED}, recibio '{wh}'. "
            "Configura la env var WAREHOUSE_TYPE o pasala explicita."
        )

    if wh == "snowflake":
        return _connect_snowflake(overrides)
    if wh == "bigquery":
        return _connect_bigquery(overrides)
    if wh == "redshift":
        return _connect_redshift(overrides)
    raise ValueError(f"Warehouse no soportado: {wh}")  # unreachable


def get_engine(warehouse_type: str | None = None) -> Engine:
    """Alias de connect_warehouse para tests."""
    return connect_warehouse(warehouse_type)


def test_connection(engine: Engine) -> bool:
    """Ejecuta SELECT 1 para validar que la conexion funciona.

    Returns True si responde. Levanta la excepcion original si falla.
    """
    with engine.connect() as conn:
        result = conn.exec_driver_sql("SELECT 1").scalar()
        return result == 1


# ---- Snowflake --------------------------------------------------------------

def _connect_snowflake(overrides: dict[str, Any]) -> Engine:
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
                "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE"]
    creds = _gather_creds(required, "snowflake", overrides)

    try:
        from snowflake.sqlalchemy import URL
        from sqlalchemy import create_engine
    except ImportError as e:
        raise MissingDependencyError(
            "snowflake-connector-python",
            "snowflake-connector-python '>=3.0'",
        ) from e

    url = URL(
        account=creds["SNOWFLAKE_ACCOUNT"],
        user=creds["SNOWFLAKE_USER"],
        password=creds["SNOWFLAKE_PASSWORD"],
        warehouse=creds["SNOWFLAKE_WAREHOUSE"],
        database=creds["SNOWFLAKE_DATABASE"],
        schema=creds.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
    )
    return create_engine(url, connect_args={"client_session_keep_alive": True})


# ---- BigQuery ---------------------------------------------------------------

def _connect_bigquery(overrides: dict[str, Any]) -> Engine:
    required = ["WAREHOUSE_PROJECT", "WAREHOUSE_DATASET"]
    creds = _gather_creds(required, "bigquery", overrides)

    try:
        from sqlalchemy_bigquery import BigQueryDialect  # noqa: F401
        from sqlalchemy import create_engine
    except ImportError as e:
        raise MissingDependencyError(
            "sqlalchemy-bigquery",
            "sqlalchemy-bigquery google-cloud-bigquery '>=3.0'",
        ) from e

    # sqlalchemy-bigquery usa URLs tipo bigquery://project/dataset
    return create_engine(
        f"bigquery://{creds['WAREHOUSE_PROJECT']}/{creds['WAREHOUSE_DATASET']}"
    )


# ---- Redshift ---------------------------------------------------------------

def _connect_redshift(overrides: dict[str, Any]) -> Engine:
    required = ["REDSHIFT_HOST", "REDSHIFT_PORT", "REDSHIFT_USER",
                "REDSHIFT_PASSWORD", "REDSHIFT_DATABASE"]
    creds = _gather_creds(required, "redshift", overrides)

    try:
        from sqlalchemy_redshift import register_dialect  # noqa: F401
        from sqlalchemy import create_engine
    except ImportError as e:
        raise MissingDependencyError(
            "sqlalchemy-redshift",
            "sqlalchemy-redshift redshift-connector '>=2.0'",
        ) from e

    from urllib.parse import quote_plus
    host = creds["REDSHIFT_HOST"]
    port = creds["REDSHIFT_PORT"]
    user = quote_plus(creds["REDSHIFT_USER"])
    pwd = quote_plus(creds["REDSHIFT_PASSWORD"])
    db = creds["REDSHIFT_DATABASE"]
    url = f"redshift+redshift_connector://{user}:{pwd}@{host}:{port}/{db}"
    return create_engine(url)


# ---- helpers ---------------------------------------------------------------

def _gather_creds(required: list[str], warehouse: str,
                  overrides: dict[str, Any]) -> dict[str, str]:
    """Lee env vars requeridas, aplica overrides, valida."""
    out: dict[str, str] = {}
    missing: list[str] = []
    for key in required:
        val = overrides.get(key) or os.environ.get(key, "")
        if not val:
            missing.append(key)
        else:
            out[key] = val
    if missing:
        raise MissingCredentialsError(missing, warehouse)
    return out