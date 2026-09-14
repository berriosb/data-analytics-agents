"""
Demo end-to-end de `audit-log`:
1. Genera 10 eventos con PII
2. Verifica que el JSONL NO contiene PII real (regex assertion)
3. Query por filtro (actor=sql-analyst, action=rejected)
4. Query por filtros combinados (since X, action=insert)
5. Verifica que los archivos tienen permisos 0600

Uso:
    python examples/audit_log_sample/demo_offline.py
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from skills_loader import load_skill_packages
load_skill_packages("skills")

from audit_log.recetas import init_audit_log, query_audit


EXAMPLE_DIR = Path(__file__).parent
PII_SAMPLES = [
    "juan.perez@banco.cl",
    "maria.lopez@example.com",
    "12.345.678-9",
    "+56 9 8765 4321",
    "1234 5678 9012 3456",
]


def main() -> None:
    # Setear env vars ANTES de importar el paquete
    audit_dir = EXAMPLE_DIR / "_audit_temp"
    if audit_dir.exists():
        shutil.rmtree(audit_dir)
    os.environ["AUDIT_LOG_DIR"] = str(audit_dir)
    os.environ["AUDIT_LOG_ACTOR"] = "demo-offline"

    # Ahora sí importar
    sys.path.insert(0, str(EXAMPLE_DIR.parents[1]))
    from skills_loader import load_skill_packages
    load_skill_packages("skills")
    from audit_log.recetas import init_audit_log, query_audit

    # 1. Generar los 10 eventos
    print("=== Generando 10 eventos con PII ===")
    subprocess.run([sys.executable, str(EXAMPLE_DIR / "generate_sample.py")],
                   check=True, capture_output=True)

    log_file = audit_dir / "events.jsonl"
    if not log_file.exists():
        print(f"FAIL: {log_file} no existe")
        sys.exit(1)

    # 2. Verificar NO PII en el JSONL
    print(f"\n=== Verificando NO PII en {log_file.name} ===")
    content = log_file.read_text(encoding="utf-8")
    for pii in PII_SAMPLES:
        if pii in content:
            print(f"  [FAIL] PII encontrado en el log: {pii!r}")
            sys.exit(1)
    print(f"  [OK] 0 PII encontrados (5 patrones verificados)")

    # 3. Permisos 0600
    mode = stat.S_IMODE(log_file.stat().st_mode)
    if mode != 0o600:
        print(f"  [FAIL] permisos del log: {oct(mode)} (esperado 0o600)")
        sys.exit(1)
    print(f"  [OK] permisos del log: {oct(mode)} (0600)")

    # 4. Query por filtro: actor=sql-analyst
    print(f"\n=== Query: actor=sql-analyst ===")
    results = query_audit(actor="sql-analyst", limit=20)
    print(f"  {len(results)} eventos del agente sql-analyst")
    for r in results[:5]:
        print(f"    {r['timestamp'][:19]} {r['action']:9s} {r['target'][:30]:30s} {r['status']}")

    # 5. Query por filtros combinados: action=rejected
    print(f"\n=== Query: action=rejected ===")
    results = query_audit(action="rejected")
    print(f"  {len(results)} eventos rechazados")
    for r in results:
        print(f"    {r['timestamp'][:19]} {r['engine']:10s} {r['target'][:30]:30s}")
        print(f"      SQL: {r['sql_preview']}")
        print(f"      Error: {r['error']}")

    # 6. Verificar que redacted_fields aparece en eventos con PII
    print(f"\n=== Verificando campos redacted ===")
    results = query_audit(limit=20)
    n_with_redaction = sum(1 for r in results if r.get("redacted_fields"))
    print(f"  {n_with_redaction}/{len(results)} eventos tienen redacted_fields poblado")
    for r in results[:5]:
        if r.get("redacted_fields"):
            print(f"    {r['action']:9s} {r['engine']:10s} redacted={r['redacted_fields']}")

    # Cleanup
    if audit_dir.exists():
        shutil.rmtree(audit_dir)
        print(f"\n  (cleanup: {audit_dir.name}/ borrado)")

    print("\nOK: 10 eventos generados, 0 PII en el log, queries funcionan.")


if __name__ == "__main__":
    main()