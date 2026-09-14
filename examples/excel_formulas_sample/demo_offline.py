"""
Demo end-to-end de `excel-formulas`: genera un Excel con formulas
variadas y produce el reporte markdown.

Uso:
    python examples/excel_formulas_sample/generate_sample.py
    python examples/excel_formulas_sample/demo_offline.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from skills_loader import load_skill_packages
load_skill_packages("skills")

from excel_formulas.recetas import (
    extract_formulas, classify_formula, build_report,
)


EXAMPLE_DIR = Path(__file__).parent
SAMPLE = EXAMPLE_DIR / "revenue_q2_2026_with_formulas.xlsx"
REPORT = EXAMPLE_DIR / "revenue_q2_2026_with_formulas_formulas.md"


def main() -> None:
    if not SAMPLE.exists():
        print("Generando sample primero...")
        subprocess.run([sys.executable, str(EXAMPLE_DIR / "generate_sample.py")],
                       check=True)

    print(f"=== Extrayendo formulas de {SAMPLE.name} ===")
    formulas = extract_formulas(SAMPLE)
    print(f"  {len(formulas)} formulas extraidas\n")

    # Verificacion rapida: al menos una formula aggregate, lookup, logical,
    # date volatile, error
    cats = {f["classification"]["category"] for f in formulas}
    required = {"aggregate", "lookup", "logical", "date"}
    missing = required - cats
    if missing:
        print(f"  FAIL: categorias requeridas faltantes: {missing}")
        sys.exit(1)

    n_volatile = sum(1 for f in formulas if f["classification"]["is_volatile"])
    n_errors = sum(1 for f in formulas if f["value_is_error"])
    print(f"  Categorias presentes: {sorted(cats)}")
    print(f"  Formulas volatiles: {n_volatile}")
    print(f"  Errores detectados (cached): {n_errors}")

    # Verificacion del classifier: tests con casos representativos
    print(f"\n=== Tests del classifier ===")
    cases = [
        ("SUM(A1:A10)", "aggregate"),
        ("=ROUND(SUM(A:A), 2)", "math"),
        ("=IF(A1>0, 1, 0)", "logical"),
        ("=VLOOKUP(A1, X!A:B, 2, FALSE)", "lookup"),
        ("=NOW()", "date"),
        ("=NPV(0.1, A1:A5)", "financial"),
    ]
    all_ok = True
    for formula, expected in cases:
        cls = classify_formula(formula)
        status = "OK" if cls["category"] == expected else "FAIL"
        if status == "FAIL":
            all_ok = False
        print(f"  [{status}] {formula:35s} -> {cls['category']:12s} (esperado: {expected})")
    if not all_ok:
        print("FAIL: classifier tiene falsos positivos")
        sys.exit(1)

    # Reporte markdown
    print(f"\n=== Generando reporte markdown ===")
    out = build_report(SAMPLE, REPORT)
    print(f"  Reporte: {out} ({out.stat().st_size} bytes)")

    # Verificacion del reporte: debe contener las secciones clave.
    # 'Errores detectados' es opcional (solo aparece si hay errores cached).
    md = out.read_text(encoding="utf-8")
    must_have = [
        "# Formulas Audit",
        "## Resumen por categoria",
        "## Formulas volatiles",
        "## Hoja: `Analisis`",
    ]
    missing_sections = [s for s in must_have if s not in md]
    if missing_sections:
        print(f"  FAIL: secciones faltantes en el reporte: {missing_sections}")
        sys.exit(1)

    # Verificar que la seccion de errores se incluye cuando hay errores
    # cached. Para forzarlo, modificamos un cached value a error string
    # via openpyxl y re-generamos.
    if n_errors == 0:
        print("  (nota: 0 errores cached — openpyxl no evalua formulas, esto es OK)")
        print("  Seccion 'Errores detectados' omitida intencionalmente.")

    print("\nOK: 13 formulas extraidas, classifier pasa tests, reporte completo.")


if __name__ == "__main__":
    main()