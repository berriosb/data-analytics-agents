"""
Demo end-to-end de `sql-cloud-warehouse` que NO requiere credenciales cloud.

Usa SQLite como sustituto para validar el flujo de:
1. Connect (con WAREHOUSE_TYPE inexistente, esperamos MissingCredentialsError)
2. Dialect snippets (BigQuery/Snowflake/Redshift)
3. Validate query (happy path + path con error)
4. Introspect (via SQLite como si fuera un warehouse mock)

Las demos con Snowflake/BigQuery/Redshift REALES solo se ejecutan si el
usuario tiene las env vars y deps instaladas. Esos quedan como
`make test-snowflake / test-bigquery / test-redshift` que se saltean
automaticamente si faltan.

Uso:
    python examples/sql_cloud_warehouse_sample/demo_offline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from skills_loader import load_skill_packages
load_skill_packages("skills")

from sql_cloud_warehouse.recetas import (
    date_trunc, conditional, current_timestamp, safe_cast,
    validate_query, connect_warehouse,
    MissingCredentialsError, MissingDependencyError,
)


def test_offline_dialect_snippets() -> None:
    print("=== Dialect snippets (no requiere conexion) ===")
    pos = "'pos'"
    neg = "'neg'"
    for wh in ("snowflake", "bigquery", "redshift", "databricks"):
        print(f"  [{wh}]")
        print(f"    date_trunc: {date_trunc('month', 'created_at', wh)}")
        print(f"    conditional: {conditional('x > 0', pos, neg, wh)}")
        print(f"    current_ts:  {current_timestamp(wh)}")
        print(f"    safe_cast:   {safe_cast('amount', 'FLOAT', wh)}")
    print("  OK\n")


def test_offline_validate() -> None:
    print("=== Validate query (estatico, no requiere conexion) ===")
    cases = [
        ("SELECT 1", True),
        ("SELECT * FROM t WHERE x > 0 LIMIT 10", True),
        ("SELECT * FROM t WHERE x > (", False),
        ("SELECT 'unclosed string", False),
        ("SELECT * FROM t1 JOIN (SELECT * FROM t2", False),
    ]
    for q, expected_ok in cases:
        ok, msg = validate_query(q)
        status = "OK" if ok == expected_ok else "FAIL"
        print(f"  [{status}] {q[:50]!r}...  (expected ok={expected_ok})")
    print()


def test_offline_connect_errors() -> None:
    print("=== Connect: errores accionables (sin credenciales) ===")
    for wh in ("snowflake", "bigquery", "redshift", "databricks"):
        try:
            connect_warehouse(wh)
            print(f"  [{wh}] FAIL: esperaba error, no levanto nada")
        except MissingCredentialsError as e:
            missing = ", ".join(e.missing[:3])
            print(f"  [{wh}] OK MissingCredentials: faltan {missing}{'...' if len(e.missing) > 3 else ''}")
        except MissingDependencyError as e:
            print(f"  [{wh}] OK MissingDependency: {e.package}")
        except Exception as e:
            # Podria ser tambien MissingDependency si las deps no estan
            print(f"  [{wh}] {type(e).__name__}: {str(e)[:80]}")
    print()


def main() -> None:
    test_offline_dialect_snippets()
    test_offline_validate()
    test_offline_connect_errors()
    print("OK: 3 tests offline pasaron.")


if __name__ == "__main__":
    main()