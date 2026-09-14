"""
Genera un Excel de muestra con formulas variadas para probar
`excel-formulas`. Produce ~15 celdas con formula cubriendo:
- Aggregate (SUM, AVERAGE)
- Lookup (VLOOKUP)
- Logical (IF, IFERROR)
- Math (ROUND, ABS)
- Date (NOW volatile)
- Error (#REF!)
- Cross-sheet reference

Uso:
    python examples/excel_formulas_sample/generate_sample.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font


EXAMPLE_DIR = Path(__file__).parent
OUT_FILE = EXAMPLE_DIR / "revenue_q2_2026_with_formulas.xlsx"


def main() -> None:
    wb = Workbook()

    # Hoja 1: Datos crudos
    ws_data = wb.active
    ws_data.title = "Data"
    ws_data.append(["cliente_id", "revenue", "costs"])
    rows_data = [
        (1, 1500, 800),
        (2, 2300, 1100),
        (3, 950, 600),
        (4, 3200, 1900),
        (5, 1100, 700),
    ]
    for r in rows_data:
        ws_data.append(r)
    # Datos adicionales para lookup
    ws_data["E1"] = "segmento"
    ws_data["F1"] = "nombre"
    ws_data["E2"] = "Enterprise"; ws_data["F2"] = "ACME Corp"
    ws_data["E3"] = "Enterprise"; ws_data["F3"] = "Globex"
    ws_data["E4"] = "SMB";          ws_data["F4"] = "Initech"
    ws_data["E5"] = "Enterprise"; ws_data["F5"] = "Hooli"
    ws_data["E6"] = "Mid-market";   ws_data["F6"] = "Pied Piper"

    # Hoja 2: Analisis (con formulas)
    ws = wb.create_sheet("Analisis")
    bold = Font(bold=True)

    # Header
    ws["A1"] = "Metrica"
    ws["B1"] = "Valor"
    ws["C1"] = "Formula"
    for cell in (ws["A1"], ws["B1"], ws["C1"]):
        cell.font = bold

    # SUM, AVERAGE, MAX, MIN (aggregate)
    ws["A2"] = "Total revenue Q2"
    ws["B2"] = "=SUM(Data!B2:B6)"
    ws["C2"] = "Aggregate"

    ws["A3"] = "Promedio revenue"
    ws["B3"] = "=AVERAGE(Data!B2:B6)"
    ws["C3"] = "Aggregate"

    ws["A4"] = "Max revenue"
    ws["B4"] = "MAX(Data!B2:B6)"
    ws["C4"] = "Aggregate (prefijo '=' omitido para test)"

    # Lookup
    ws["A5"] = "Segmento cliente 1"
    ws["B5"] = "=VLOOKUP(1, Data!A2:E6, 5, FALSE)"
    ws["C5"] = "Lookup"

    # Logical
    ws["A6"] = "Revenue sobre 1000?"
    ws["B6"] = '=IF(SUM(Data!B2:B6)>10000, "alto", "bajo")'
    ws["C6"] = "Logical"

    ws["A7"] = "Total safe (IFERROR)"
    ws["B7"] = '=IFERROR(SUM(Data!B2:B6)/0, "division por cero")'
    ws["C7"] = "Logical"

    # Math
    ws["A8"] = "Total redondeado"
    ws["B8"] = "=ROUND(SUM(Data!B2:B6), 2)"
    ws["C8"] = "Math"

    ws["A9"] = "Diferencia revenue max - min"
    ws["B9"] = "=ABS(MAX(Data!B2:B6)-MIN(Data!B2:B6))"
    ws["C9"] = "Math"

    # Cross-sheet
    ws["A10"] = "Total costs"
    ws["B10"] = "=SUM(Data!C2:C6)"
    ws["C10"] = "Cross-sheet reference"

    # Margin
    ws["A11"] = "Margen %"
    ws["B11"] = "=IFERROR((B2-B10)/B2, 0)"
    ws["C11"] = "Logical (compuesta)"

    # Volatile
    ws["A12"] = "Timestamp auditoria"
    ws["B12"] = "=NOW()"
    ws["C12"] = "Date (volatile)"

    # Error
    ws["A13"] = "Lookup que falla"
    ws["B13"] = "=VLOOKUP(999, Data!A2:E6, 5, FALSE)"
    ws["C13"] = "Lookup (debe dar #N/A)"

    ws["A14"] = "Referencia rota"
    ws["B14"] = "=SUM(Data!Z1:Z99)"
    ws["C14"] = "Error (#REF! o vacio segun version de openpyxl)"

    # Anidada
    ws["A15"] = "Total redondeado + IF"
    ws["B15"] = '=IF(ROUND(SUM(Data!B2:B6), 0) > 10000, ROUND(SUM(Data!B2:B6)/12, 2), 0)'
    ws["C15"] = "Logical+Math (compuesta, complex)"

    wb.save(OUT_FILE)
    size_kb = OUT_FILE.stat().st_size / 1024
    print(f"OK: sample generado ({size_kb:.1f} KB) en {OUT_FILE}")
    print(f"   {15} celdas con formulas cubriendo {6} categorias")


if __name__ == "__main__":
    main()