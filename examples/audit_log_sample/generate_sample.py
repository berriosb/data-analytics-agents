"""
Genera eventos de muestra con PII embebido para probar `audit-log`.

Crea 10 eventos:
- 4 SELECT (varios engines)
- 3 INSERT (incluido uno con error)
- 1 CREATE
- 2 rejected (DROP/UPDATE bloqueados por sql-write)

Uso:
    python examples/audit_log_sample/generate_sample.py
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


EXAMPLE_DIR = Path(__file__).parent


def main() -> None:
    # 1) Setear env vars ANTES de cualquier import del paquete.
    audit_dir = EXAMPLE_DIR / "_audit_temp"
    if audit_dir.exists():
        shutil.rmtree(audit_dir)
    os.environ["AUDIT_LOG_DIR"] = str(audit_dir)
    os.environ["AUDIT_LOG_ACTOR"] = "data-explorer-agent"

    # 2) Recién ahora importar (backend.py leera AUDIT_LOG_DIR al module load).
    sys.path.insert(0, str(EXAMPLE_DIR.parents[1]))
    from skills_loader import load_skill_packages
    load_skill_packages("skills")
    from audit_log.recetas import init_audit_log, audit_log, audit_event

    init_audit_log(backend="jsonl")

    print("=== Generando 10 eventos con PII embebido ===")

    events = [
        dict(actor="data-explorer", action="select", engine="sqlite",
             target="clientes", status="ok", n_rows=30,
             sql_preview="SELECT * FROM clientes WHERE email = 'juan.perez@banco.cl'"),
        dict(actor="data-explorer", action="select", engine="snowflake",
             target="analytics.transactions", status="ok", n_rows=1000,
             sql_preview="SELECT cliente_id, monto FROM transactions WHERE cliente_rut = '12.345.678-9'"),
        dict(actor="reporting-analyst", action="select", engine="bigquery",
             target="warehouse.events", status="failed", n_rows=0,
             duration_ms=2300,
             sql_preview="SELECT * FROM events WHERE contact = '+56 9 8765 4321'",
             error="Permission denied: project dataset"),
        dict(actor="reporting-analyst", action="select", engine="postgres",
             target="audit.users", status="ok", n_rows=5,
             sql_preview="SELECT user_id, name FROM users"),

        dict(actor="sql-analyst", action="insert", engine="sqlite",
             target="top_clients_q2_2026", status="ok", n_rows=5,
             duration_ms=42,
             sql_preview="INSERT INTO top_clients_q2_2026 (cliente_id, nombre, revenue, segmento) VALUES (1, 'ACME Corp', 2300.0, 'Enterprise')"),
        dict(actor="sql-analyst", action="insert", engine="snowflake",
             target="analytics.predictions_q2", status="ok", n_rows=100,
             duration_ms=1200,
             sql_preview="INSERT INTO predictions_q2 SELECT * FROM model_output"),
        dict(actor="sql-analyst", action="insert", engine="sqlite",
             target="bad_table", status="failed", n_rows=0,
             duration_ms=15,
             sql_preview="INSERT INTO bad_table VALUES (1)",
             error="UNIQUE constraint failed: bad_table.id"),

        dict(actor="sql-analyst", action="create", engine="sqlite",
             target="new_metrics", status="ok", n_rows=0,
             sql_preview="CREATE TABLE IF NOT EXISTS new_metrics (id INTEGER, value REAL)"),

        dict(actor="sql-analyst", action="rejected", engine="postgres",
             target="legacy.users", status="rejected", n_rows=0,
             sql_preview="DROP TABLE legacy.users",
             error="BlockedOperationError: DROP no permitido en modo conservador"),
        dict(actor="sql-analyst", action="rejected", engine="postgres",
             target="audit.users", status="rejected", n_rows=0,
             sql_preview="UPDATE audit.users SET password = 'hacked'",
             error="BlockedOperationError: UPDATE no permitido en modo conservador"),
    ]

    for i, e in enumerate(events, 1):
        audit_log(audit_event(**e))
        print(f"  [{i:2d}/10] {e['action']:9s} {e['engine']:10s} {e['target'][:30]:30s} {e['status']}")

    print(f"\nAudit log escrito en: {audit_dir}/events.jsonl")


if __name__ == "__main__":
    main()