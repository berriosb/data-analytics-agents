"""
Clasificacion heuristica de formulas Excel por tipo y deteccion de
features especiales (volatile, error, shared, array).

Categorias:
- aggregate: SUM, AVERAGE, COUNT, MAX, MIN, PRODUCT, ...
- lookup: VLOOKUP, HLOOKUP, INDEX, MATCH, XLOOKUP, OFFSET
- logical: IF, IFS, AND, OR, NOT, IFERROR, ISERROR
- text: CONCAT, CONCATENATE, LEFT, RIGHT, MID, LEN, TRIM, UPPER, LOWER
- date: NOW, TODAY, DATE, YEAR, MONTH, DAY, DATEDIF, NETWORKDAYS
- financial: NPV, IRR, PMT, FV, PV, RATE
- math: ABS, ROUND, CEILING, FLOOR, MOD, POWER, SQRT
- info: ISBLANK, ISNUMBER, ISTEXT, ISERROR, TYPE
- other: todo lo que no matchee las anteriores
"""

from __future__ import annotations

import re
from typing import Any


FORMULA_CATEGORIES = (
    "aggregate", "lookup", "logical", "text", "date",
    "financial", "math", "info", "error", "volatile", "other",
)

_VOLATILE_FUNCTIONS = {
    "NOW", "TODAY", "RAND", "RANDBETWEEN", "OFFSET", "INDIRECT",
    "INFO", "CELL",
}

_ERROR_VALUES = {
    "#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!",
    "#N/A", "#GETTING_DATA", "#SPILL!", "#CALC!",
}


def classify_formula(formula_str: str) -> dict[str, Any]:
    """Clasifica una formula Excel y devuelve metadata estructurada.

    Args:
        formula_str: la formula tal como la devuelve openpyxl (sin '=' al inicio
            en algunas versiones; lo manejamos ambos casos).

    Returns:
        {
            "category": str,            # una de FORMULA_CATEGORIES
            "functions_used": [str],    # nombres de funciones en MAYUSCULAS
            "is_volatile": bool,         # usa alguna funcion volatile
            "is_array": bool,           # formula array (heuristica por brackets {})
            "is_shared": bool,          # shared formula (heuristica, openpyxl no expone directo)
            "has_error": bool,          # la formula contiene un error literal
            "complexity": str,          # 'simple' | 'medium' | 'complex'
        }
    """
    if not formula_str:
        return {
            "category": "other",
            "functions_used": [],
            "is_volatile": False,
            "is_array": False,
            "is_shared": False,
            "has_error": False,
            "complexity": "simple",
        }

    s = formula_str.strip()
    # Quitar '=' inicial si esta
    if s.startswith("="):
        s = s[1:]

    # Extraer funciones (palabras seguidas de '(' en MAYUSCULAS)
    func_matches = re.findall(r"\b([A-Z][A-Z0-9_\.]+)\s*\(", s)
    funcs = list(dict.fromkeys(func_matches))  # dedupe preservando orden

    has_error = any(err in s for err in _ERROR_VALUES)
    is_volatile = any(f in _VOLATILE_FUNCTIONS for f in funcs)
    is_array = s.startswith("{") and s.endswith("}")
    # Shared formula: openpyxl lo expone en cell.shared_formula attribute,
    # no en cell.value. Lo dejamos como heuristica off por default.
    is_shared = False

    # Categoria — se elije la MAS ESPECIFICA entre las que matchean.
    # Aggregate es la menos especifica (siempre matchea para SUM), asi que
    # se evalua al final como fallback.
    category = "other"
    if has_error:
        category = "error"
    elif any(f in {"NPV", "IRR", "PMT", "FV", "PV", "RATE", "NPER",
                    "SLN", "DB", "DDB", "VDB", "XNPV", "XIRR"} for f in funcs):
        category = "financial"
    elif any(f in {"VLOOKUP", "HLOOKUP", "XLOOKUP", "INDEX", "MATCH",
                    "OFFSET", "INDIRECT", "CHOOSE", "ROW", "COLUMN"} for f in funcs):
        category = "lookup"
    elif any(f in {"CONCAT", "CONCATENATE", "LEFT", "RIGHT", "MID", "LEN",
                    "TRIM", "UPPER", "LOWER", "PROPER", "TEXT", "VALUE",
                    "SEARCH", "FIND", "REPLACE", "SUBSTITUTE"} for f in funcs):
        category = "text"
    elif any(f in {"NOW", "TODAY", "DATE", "YEAR", "MONTH", "DAY", "HOUR",
                    "MINUTE", "SECOND", "DATEDIF", "NETWORKDAYS", "WEEKDAY",
                    "EOMONTH", "EDATE"} for f in funcs):
        category = "date"
    elif any(f in {"ABS", "ROUND", "ROUNDUP", "ROUNDDOWN", "CEILING",
                    "FLOOR", "MOD", "POWER", "SQRT", "EXP", "LN", "LOG",
                    "SIN", "COS", "TAN", "PI"} for f in funcs):
        category = "math"
    elif any(f in {"IF", "IFS", "AND", "OR", "NOT", "IFERROR", "ISERROR",
                    "ISBLANK", "ISNUMBER", "ISTEXT", "ISLOGICAL", "IFNA",
                    "SWITCH"} for f in funcs):
        category = "logical"
    elif any(f in {"ISBLANK", "ISNUMBER", "ISTEXT", "ISERROR", "TYPE",
                    "ISNONTEXT", "ISLOGICAL"} for f in funcs):
        category = "info"
    elif any(f in {"SUM", "AVERAGE", "COUNT", "COUNTA", "MAX", "MIN",
                    "PRODUCT", "SUMIF", "SUMIFS", "AVERAGEIF", "AVERAGEIFS",
                    "COUNTIF", "COUNTIFS", "MEDIAN", "STDEV", "VAR"} for f in funcs):
        category = "aggregate"

    # Complejidad (heuristica: numero de funciones + niveles de anidamiento)
    depth = _max_depth(s)
    func_count = len(funcs)
    if func_count <= 1 and depth <= 1:
        complexity = "simple"
    elif func_count <= 3 and depth <= 2:
        complexity = "medium"
    else:
        complexity = "complex"

    return {
        "category": category,
        "functions_used": funcs,
        "is_volatile": is_volatile,
        "is_array": is_array,
        "is_shared": is_shared,
        "has_error": has_error,
        "complexity": complexity,
    }


def _max_depth(formula: str) -> int:
    """Calcula la profundidad maxima de parentesis anidados."""
    depth = 0
    max_d = 0
    for ch in formula:
        if ch == "(":
            depth += 1
            max_d = max(max_d, depth)
        elif ch == ")":
            depth = max(0, depth - 1)
    return max_d