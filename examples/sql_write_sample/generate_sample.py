"""
Genera un CSV de muestra con los top-5 clientes por revenue Q2 2026.
El demo de sql-write lo carga, valida el SQL (CREATE TABLE + INSERT),
hace dry-run, ejecuta, y verifica el audit log.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


EXAMPLE_DIR = Path(__file__).parent
OUT_CSV = EXAMPLE_DIR / "top_clients_q2_2026.csv"


def main() -> None:
    data = [
        {"cliente_id": 1, "nombre": "ACME Corp",   "revenue": 2300.0, "segmento": "Enterprise"},
        {"cliente_id": 2, "nombre": "Globex",      "revenue": 1800.0, "segmento": "Enterprise"},
        {"cliente_id": 3, "nombre": "Initech",     "revenue": 1200.0, "segmento": "Mid-market"},
        {"cliente_id": 4, "nombre": "Hooli",       "revenue":  950.0, "segmento": "Mid-market"},
        {"cliente_id": 5, "nombre": "Pied Piper",  "revenue":  800.0, "segmento": "SMB"},
    ]
    df = pd.DataFrame(data)
    df.to_csv(OUT_CSV, index=False)
    print(f"OK: {len(df)} filas en {OUT_CSV} ({OUT_CSV.stat().st_size} bytes)")


if __name__ == "__main__":
    main()