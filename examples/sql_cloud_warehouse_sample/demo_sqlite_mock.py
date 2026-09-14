"""
Demo end-to-end CON SQLite como sustituto de warehouse cloud.

Crea una DB SQLite local con 2 tablas y un par de JOIN paths, luego la
introspecciona usando `introspect_schema` (que normalmente apunta a
INFORMATION_SCHEMA de Snowflake/BQ/Redshift pero SQLite responde a la
misma query con INFORMATION_SCHEMA nativo).

Esto valida el flujo de introspeccion + JOIN discovery sin necesitar
credenciales cloud. Los snippets dialecto-aware ya estan probados en
`demo_offline.py`.

Uso:
    python examples/sql_cloud_warehouse_sample/demo_sqlite_mock.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from skills_loader import load_skill_packages
load_skill_packages("skills")

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("  SKIPPED: sqlalchemy no instalada (pip install sqlalchemy)")
    sys.exit(0)

from sql_cloud_warehouse.recetas import introspect_schema


def main() -> None:
    db_path = Path(__file__).parent / "mock_warehouse.sqlite"
    if db_path.exists():
        db_path.unlink()

    # Setup: 2 tablas relacionadas (customers + orders)
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            country TEXT
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER REFERENCES customers(id),
            amount REAL,
            created_at TEXT
        );
        INSERT INTO customers (id, name, country) VALUES
            (1, 'ACME Corp', 'CL'),
            (2, 'Globex', 'AR'),
            (3, 'Initech', 'CL');
        INSERT INTO orders (id, customer_id, amount, created_at) VALUES
            (1, 1, 1500.0, '2026-04-15'),
            (2, 1, 2300.0, '2026-05-20'),
            (3, 2, 800.0,  '2026-06-01'),
            (4, 3, 950.0,  '2026-06-12');
    """)
    con.close()

    engine = create_engine(f"sqlite:///{db_path}")
    info = introspect_schema(engine, schema="main")

    print(f"=== Introspeccion de SQLite mock ===")
    print(f"  warehouse: {info['warehouse']}")
    print(f"  schema:    {info['schema']}")
    print(f"  tablas:    {len(info['tables'])}")
    for tname, cols in info["tables"].items():
        col_str = ", ".join(f"{c['name']}:{c['type']}" for c in cols)
        print(f"    - {tname}({col_str})")
    print()

    # Smoke test de una query con JOIN
    print("=== Query de smoke test ===")
    sql = """
    SELECT c.country, SUM(o.amount) AS total
    FROM customers c JOIN orders o ON c.id = o.customer_id
    GROUP BY c.country
    ORDER BY total DESC
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).fetchall()
        for r in rows:
            print(f"  {r[0]}: {r[1]}")

    print()
    print(f"OK: introspeccion + query ejecutadas (DB mock en {db_path})")
    print(f"   (la DB queda en disco; podes borrarla cuando quieras)")


if __name__ == "__main__":
    main()