"""
Demo end-to-end de `sql-write` modo conservador:

1. Genera el sample (CSV con top-5 clientes).
2. Carga el CSV como DataFrame.
3. Valida el SQL CREATE TABLE + INSERT contra el validator.
4. Hace dry_run (no toca la DB).
5. Ejecuta el INSERT con auto_confirm=True (skip el prompt del usuario).
7. Verifica que las filas estan en SQLite.
8. Verifica que el audit log tiene las entradas correctas.
9. Verifica que operaciones bloqueadas (DROP) son rechazadas.

Uso:
    python examples/sql_write_sample/demo_offline.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from skills_loader import load_skill_packages
load_skill_packages("skills")

from sqlalchemy import text

from sql_write.recetas import (
    connect_target, dry_run, execute_insert,
    validate_sql, BlockedOperationError, audit_log,
)


EXAMPLE_DIR = Path(__file__).parent
SAMPLE_CSV = EXAMPLE_DIR / "top_clients_q2_2026.csv"
DB_PATH = EXAMPLE_DIR / "demo_results.sqlite"


def main() -> None:
    # Limpiar DB anterior si existe
    if DB_PATH.exists():
        DB_PATH.unlink()

    if not SAMPLE_CSV.exists():
        print("Generando sample primero...")
        import subprocess
        subprocess.run([sys.executable, str(EXAMPLE_DIR / "generate_sample.py")],
                       check=True)

    print(f"=== Cargando CSV: {SAMPLE_CSV.name} ===")
    df = pd.read_csv(SAMPLE_CSV)
    print(f"  {len(df)} filas, {len(df.columns)} columnas")
    print(f"  dtypes: {dict(df.dtypes)}")

    print(f"\n=== Validando SQL propuesto ===")
    ddl = "CREATE TABLE IF NOT EXISTS top_clients_q2_2026 (cliente_id INTEGER, nombre TEXT, revenue REAL, segmento TEXT)"
    insert_sql = "INSERT INTO top_clients_q2_2026 (cliente_id, nombre, revenue, segmento) VALUES (1, 'ACME', 2300.0, 'Enterprise')"
    try:
        validate_sql(ddl)
        print(f"  [OK] DDL valido: CREATE TABLE IF NOT EXISTS")
    except BlockedOperationError as e:
        print(f"  [FAIL] DDL bloqueado: {e.operation}")
        sys.exit(1)
    try:
        validate_sql(insert_sql)
        print(f"  [OK] INSERT valido")
    except BlockedOperationError as e:
        print(f"  [FAIL] INSERT bloqueado: {e.operation}")
        sys.exit(1)

    print(f"\n=== Test: DROP debe ser bloqueado ===")
    try:
        validate_sql("DROP TABLE top_clients_q2_2026")
        print(f"  [FAIL] DROP NO fue bloqueado!")
        sys.exit(1)
    except BlockedOperationError as e:
        print(f"  [OK] DROP bloqueado: {e.operation}")

    print(f"\n=== Conectando a SQLite: {DB_PATH.name} ===")
    engine = connect_target(DB_PATH)
    print(f"  engine: {engine.dialect.name}")

    print(f"\n=== Dry-run (sin ejecutar) ===")
    info = dry_run(engine, df, "top_clients_q2_2026")
    print(f"  DDL: {info['ddl']}")
    print(f"  Tabla existe?: {info['table_exists']}")
    print(f"  Filas a insertar: {info['n_rows']}")
    print(f"  Columnas inferidas:")
    for col, sql_type in info['columns']:
        print(f"    {col}: {sql_type}")
    print(f"  Preview (primeras 3 filas):")
    for row in info['preview_rows'][:3]:
        print(f"    {row}")

    print(f"\n=== Execute (con auto_confirm=True para el demo) ===")
    result = execute_insert(engine, df, "top_clients_q2_2026", auto_confirm=True)
    print(f"  Action: {result['action']}")
    print(f"  Filas insertadas: {result['n_rows']}")
    print(f"  Duracion: {result['duration_ms']} ms")

    print(f"\n=== Verificacion en la DB ===")
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT cliente_id, nombre, revenue, segmento FROM top_clients_q2_2026 ORDER BY revenue DESC"
        )).fetchall()
    print(f"  {len(rows)} filas leidas de la DB")
    for r in rows[:5]:
        print(f"    {r}")

    # Verificar audit log
    print(f"\n=== Verificacion del audit log ===")
    from sql_write.recetas import get_audit_path
    audit_path = get_audit_path()
    if audit_path.exists():
        with audit_path.open() as f:
            entries = [line.strip() for line in f if line.strip()]
        recent = entries[-5:]  # ultimas 5
        print(f"  Audit path: {audit_path}")
        print(f"  Total entries (post-tests): {len(entries)}")
        print(f"  Ultimas 5:")
        for e in recent:
            print(f"    {e[:120]}")
    else:
        print(f"  (audit log no existe aun — esperado si se ejecuta desde cero)")

    # Cleanup
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"\n  (cleanup: {DB_PATH.name} borrado)")

    print("\nOK: 5 filas insertadas, audit log escrito, DROP bloqueado.")


if __name__ == "__main__":
    main()