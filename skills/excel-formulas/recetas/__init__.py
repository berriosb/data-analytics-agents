"""
Recetas pre-aprobadas para extraer y analizar formulas de un Excel
corporativo (.xlsx/.xls).

Modulos:
- extract: carga workbook en modo formula-only (data_only=False),
  devuelve lista de celdas con formula + valor cached + clasificacion
- classify: heuristica para categorizar formulas (aggregate, lookup,
  logical, text, date, error, volatile, other) y detectar errores
  (#REF!, #DIV/0!, etc.)
- report: genera reporte markdown por hoja + resumen agregado
- errors: excepcion custom para problemas del archivo (protegido,
  corrupto, etc.)

Usa openpyxl (peerDep opcional ya declarada) como base. La libreria
'formulas' es OPCIONAL para el modulo de dependencias — si no esta,
build_report funciona igual pero sin la seccion de dependencias.
"""

from __future__ import annotations

from .extract import extract_formulas
from .classify import classify_formula, FORMULA_CATEGORIES
from .report import build_report
from .errors import ExcelFormulaError

__all__ = [
    "extract_formulas",
    "classify_formula",
    "FORMULA_CATEGORIES",
    "build_report",
    "ExcelFormulaError",
]