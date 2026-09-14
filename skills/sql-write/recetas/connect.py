"""
Conexion a la DB target: SQLite local o cloud warehouses via
sql-cloud-warehouse.

Soporta:
- SQLite: ruta local a archivo .sqlite/.db
- Snowflake / BigQuery / Redshift: via connect_warehouse de
  sql-cloud-warehouse (peerDeps opcionales)
- Postgres / MySQL: NO en v1 (queda como follow-up)

Returns:
    Un SQLAlchemy Engine listo para usar.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from sqlalchemy import create_engine
    from sqlalchemy.engine import Engine
except ImportError:
    create_engine = None  # type: ignore
    Engine = Any  # type: ignore


def connect_target(target: str | Path | dict[str, Any]) -> Engine:
    """Conecta al target.

    Args:
        target: si es str/Path, se trata como SQLite local.
            Si es dict, debe tener {engine: 'sqlite'|'snowflake'|'bigquery'|
            'redshift', path: ...} o las env vars que espera
            sql-cloud-warehouse.

    Raises:
        ValueError si el engine no es soportado en v1.
        MissingCredentialsError / MissingDependencyError si target=cloud
            y faltan env vars o drivers.
    """
    if isinstance(target, (str, Path)):
        return _connect_sqlite(Path(target))

    if isinstance(target, dict):
        engine = target.get("engine", "sqlite").lower()
        if engine == "sqlite":
            path = target.get("path")
            if not path:
                raise ValueError(
                    "SQLite target requiere 'path' (ruta al archivo .sqlite/.db)"
                )
            return _connect_sqlite(Path(path))
        if engine in {"snowflake", "bigquery", "redshift"}:
            return _connect_cloud(engine, target)
        raise ValueError(
            f"Engine '{engine}' no soportado en sql-write v1. "
            "Usa 'sqlite' o uno de los cloud warehouses (requiere WAREHOUSE_TYPE + env vars)."
        )

    raise TypeError(f"target debe ser str/Path o dict, recibio {type(target).__name__}")


def _connect_sqlite(path: Path) -> Engine:
    """SQLite local: archivo .sqlite/.db. Crea el archivo si no existe."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
    url = f"sqlite:///{path}"
    return create_engine(url)


def _connect_cloud(engine_type: str, target: dict[str, Any]) -> Engine:
    """Reusa connect_warehouse de sql-cloud-warehouse (peerDeps opcionales)."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    # Import lazy para no requerir peerDeps cuando se usa solo SQLite
    from skills_loader import load_skill_packages
    load_skill_packages("skills")
    from sql_cloud_warehouse.recetas import connect_warehouse

    # Si el usuario pasa creds en el target, las mergeamos con env vars
    overrides = {k.upper(): v for k, v in target.items()
                 if k.upper().startswith(("SNOWFLAKE_", "REDSHIFT_", "WAREHOUSE_",
                                          "GOOGLE_APPLICATION_CREDENTIALS"))}
    return connect_warehouse(engine_type, **overrides)