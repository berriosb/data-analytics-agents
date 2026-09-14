"""
Genera un reporte markdown con las formulas extraidas de un Excel.

Estructura del reporte:
1. Metadata del workbook (hojas, total de formulas, errores detectados)
2. Resumen por categoria (aggregate, lookup, logical, etc.)
3. Tabla detallada por hoja: celda | formula | valor | categoria | flags
4. Lista de formulas volatiles (NOW, RAND, OFFSET) con warning
5. Lista de errores (#REF!, #DIV/0!, etc.) con la celda exacta
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .extract import extract_formulas


def build_report(workbook_path: str | Path,
                 output_path: str | Path | None = None,
                 sheet_name: str | None = None) -> Path:
    """Extrae formulas y genera un reporte markdown.

    Args:
        workbook_path: ruta al .xlsx
        output_path: donde escribir el .md. Si None, va al lado del
            workbook con sufijo `_formulas.md`
        sheet_name: nombre de la hoja. Si None, todas.

    Returns:
        Path al reporte generado.
    """
    p = Path(workbook_path)
    formulas = extract_formulas(p, sheet_name)

    if output_path is None:
        output_path = p.with_name(p.stem + "_formulas.md")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    md = _render_markdown(p, formulas, sheet_name)
    output_path.write_text(md, encoding="utf-8")
    return output_path


def _render_markdown(workbook_path: Path,
                     formulas: list[dict[str, Any]],
                     sheet_filter: str | None) -> str:
    lines: list[str] = []

    # Metadata
    sheets = sorted({f["sheet"] for f in formulas})
    total = len(formulas)
    errors = [f for f in formulas if f["value_is_error"]
              or f["classification"]["has_error"]]
    volatiles = [f for f in formulas if f["classification"]["is_volatile"]]
    categories = Counter(f["classification"]["category"] for f in formulas)

    lines.append(f"# Formulas Audit: `{workbook_path.name}`")
    lines.append("")
    lines.append(f"- **Path:** `{workbook_path}`")
    lines.append(f"- **Hojas analizadas:** {len(sheets)}" + (
        f" ({', '.join(sheets)})" if sheets else ""
    ))
    if sheet_filter:
        lines.append(f"- **Filtro aplicado:** solo hoja `{sheet_filter}`")
    lines.append(f"- **Total formulas:** {total}")
    lines.append(f"- **Errores detectados:** {len(errors)}")
    lines.append(f"- **Formulas volatiles:** {len(volatiles)} (NOW, RAND, OFFSET, INDIRECT)")
    lines.append("")

    # Resumen por categoria
    lines.append("## Resumen por categoria")
    lines.append("")
    lines.append("| Categoria | Cantidad | % |")
    lines.append("|---|---:|---:|")
    if total > 0:
        for cat, count in categories.most_common():
            pct = 100 * count / total
            lines.append(f"| {cat} | {count} | {pct:.1f}% |")
    else:
        lines.append("| (sin formulas) | 0 | - |")
    lines.append("")

    # Errores
    if errors:
        lines.append("## Errores detectados")
        lines.append("")
        for f in errors:
            err_marker = " (cached value es error)" if f["value_is_error"] else ""
            lines.append(
                f"- `{f['sheet']}!{f['cell']}` — `{f['formula'][:80]}`"
                f"{err_marker}"
            )
        lines.append("")

    # Volatiles
    if volatiles:
        lines.append("## Formulas volatiles (no confiables para auditoria temporal)")
        lines.append("")
        lines.append("> Estas funciones se recalculan cada vez que Excel abre el archivo. "
                     "El valor cached puede no representar el calculo actual.")
        lines.append("")
        for f in volatiles:
            lines.append(f"- `{f['sheet']}!{f['cell']}` — `{f['formula'][:80]}`")
        lines.append("")

    # Detalle por hoja
    by_sheet: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in formulas:
        by_sheet[f["sheet"]].append(f)

    for sheet in sheets:
        sheet_formulas = by_sheet[sheet]
        lines.append(f"## Hoja: `{sheet}` ({len(sheet_formulas)} formulas)")
        lines.append("")
        if not sheet_formulas:
            lines.append("_(sin formulas en esta hoja)_")
            lines.append("")
            continue
        lines.append("| Celda | Formula | Valor cached | Categoria | Flags |")
        lines.append("|---|---|---|---|---|")
        # Ordenar por fila, columna
        sheet_formulas.sort(key=lambda f: (f["row"], f["col"]))
        for f in sheet_formulas:
            flags = []
            if f["classification"]["is_volatile"]:
                flags.append("volatile")
            if f["classification"]["is_array"]:
                flags.append("array")
            if f["value_is_error"]:
                flags.append(f"error={f['value']}")
            flag_str = ", ".join(flags) if flags else "-"
            val_str = _value_str(f["value"])
            formula_display = f["formula"][:60] + (
                "..." if len(f["formula"]) > 60 else ""
            )
            lines.append(
                f"| `{f['cell']}` | `{formula_display}` | {val_str} | "
                f"{f['classification']['category']} | {flag_str} |"
            )
        lines.append("")

    if total == 0:
        lines.append("## No se encontraron formulas")
        lines.append("")
        lines.append("El workbook no contiene celdas con formulas. "
                     "Si esperabas ver formulas, el archivo puede tener "
                     "solo valores numericos (sin auditabilidad).")
        lines.append("")

    return "\n".join(lines)


def _value_str(v: Any) -> str:
    if v is None:
        return "(vacio)"
    if isinstance(v, float):
        if abs(v) < 1e-6:
            return "0"
        if abs(v) < 0.01 or abs(v) > 1e6:
            return f"{v:.3e}"
        return f"{v:.4f}".rstrip("0").rstrip(".")
    s = str(v)
    if len(s) > 30:
        return s[:27] + "..."
    return s