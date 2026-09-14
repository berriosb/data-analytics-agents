"""
Extraccion de formulas de un Excel usando openpyxl.

Solo lectura (data_only=False para formulas, data_only=True para el
valor cached que guardo Excel al guardar).

Output: lista de dicts con metadata por celda. NO escribe a disco —
eso lo hace report.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .classify import classify_formula
from .errors import ExcelFormulaError


_ERROR_PREFIXES = ("#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?",
                   "#NUM!", "#N/A", "#GETTING_DATA", "#SPILL!", "#CALC!")


def extract_formulas(path: str | Path,
                     sheet_name: str | None = None) -> list[dict[str, Any]]:
    """Extrae todas las formulas del workbook (o de una hoja especifica).

    Args:
        path: ruta al archivo .xlsx/.xls
        sheet_name: nombre de la hoja. Si None, recorre todas.

    Returns:
        Lista de dicts, uno por celda con formula:
            {
                "sheet": str,
                "cell": "A1",
                "row": int,
                "col": int,
                "formula": str,         # sin '=' al inicio
                "value": Any,            # valor cached (puede ser error)
                "value_is_error": bool,
                "classification": dict,  # output de classify_formula
            }

    Raises:
        ExcelFormulaError si el archivo no existe, esta protegido, o
        openpyxl no puede abrirlo.
    """
    p = Path(path)
    if not p.exists():
        raise ExcelFormulaError(f"El archivo no existe", str(p))

    # Cargar DOS veces: una para formulas, otra para valores cached
    try:
        wb_f = load_workbook(p, read_only=True, data_only=False)
        wb_v = load_workbook(p, read_only=True, data_only=True)
    except Exception as e:
        raise ExcelFormulaError(f"No se pudo abrir el workbook: {e}", str(p)) from e

    formulas: list[dict[str, Any]] = []
    sheets = [sheet_name] if sheet_name else wb_f.sheetnames

    try:
        for sname in sheets:
            if sname not in wb_f.sheetnames:
                continue
            ws_f = wb_f[sname]
            ws_v = wb_v[sname] if sname in wb_v.sheetnames else None
            for row in ws_f.iter_rows():
                for cell in row:
                    if cell.value is None:
                        continue
                    val = cell.value
                    # data_type 'f' = formula. openpyxl a veces pone el '='
                    # al inicio, a veces no.
                    is_formula = (
                        isinstance(val, str)
                        and (val.startswith("=") or cell.data_type == "f")
                    )
                    if not is_formula:
                        continue

                    formula_str = val if val.startswith("=") else f"={val}"
                    formula_text = formula_str.lstrip("=").strip()

                    # Valor cached
                    cached = None
                    if ws_v is not None:
                        try:
                            cached = ws_v.cell(row=cell.row,
                                               column=cell.column).value
                        except Exception:
                            cached = None

                    value_is_error = (
                        isinstance(cached, str)
                        and any(cached.startswith(e) for e in _ERROR_PREFIXES)
                    )

                    classification = classify_formula(formula_text)

                    formulas.append({
                        "sheet": sname,
                        "cell": cell.coordinate,
                        "row": cell.row,
                        "col": cell.column,
                        "formula": formula_text,
                        "value": cached,
                        "value_is_error": value_is_error,
                        "classification": classification,
                    })
    finally:
        wb_f.close()
        wb_v.close()

    return formulas