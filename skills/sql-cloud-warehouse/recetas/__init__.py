"""
Recetas pre-aprobadas para apuntar el toolkit a un cloud warehouse
(Snowflake, BigQuery, Redshift) usando SQLAlchemy + driver oficial.

Modulos:
- connect: dispatch por WAREHOUSE_TYPE a SQLAlchemy engine, con test
  de conexion SELECT 1 y mensaje accionable si falta una dep
- introspect: introspeccion de schema reusando schema-mapper via dialecto
- dialect_snippets: snippets SQL por warehouse (DATE_TRUNC, IFF/IF/CAST, etc.)
- validate: query-validation aplicado a la query dialecto-aware
- errors: mensajes de error consistentes

Las deps cloud (snowflake-connector-python, google-cloud-bigquery,
redshift-connector) son peerDeps OPCIONALES. Esta skill falla con mensaje
accionable si no estan instaladas, NO intenta instalarlas.
"""

from .connect import connect_warehouse, get_engine, test_connection
from .introspect import introspect_schema
from .dialect_snippets import (
    date_trunc, safe_cast, conditional, current_timestamp,
    top_n, dialect_for, DIALECTS,
)
from .validate import validate_query, explain_query
from .errors import MissingDependencyError, MissingCredentialsError

__all__ = [
    "connect_warehouse",
    "get_engine",
    "test_connection",
    "introspect_schema",
    "date_trunc",
    "safe_cast",
    "conditional",
    "current_timestamp",
    "top_n",
    "dialect_for",
    "DIALECTS",
    "validate_query",
    "explain_query",
    "MissingDependencyError",
    "MissingCredentialsError",
]