---
name: excel-profiler
description: Produce un perfil estructural de solo lectura de un archivo Excel (.xlsx/.xls) "sucio" — detecta automáticamente la hoja con datos (vs. hojas de portada/metadata), la fila real de headers (frecuente en fila 3-7 entre merged cells), y reporta merged cells, columnas con >30% nulos, dtypes mezclados y columnas constantes. Úsese al primer encuentro con un Excel corporativo antes de pasar a pandas-cleaning.
---

# Excel Profiler

Solo lectura. Produce un reporte en markdown. Nunca modifica el archivo de
origen. Diseñado específicamente para los Excels "feos" del mundo corporativo:
hojas con logos y títulos, headers en filas intermedias, merged cells, columnas
mezcladas con metadata, totales al final mal formateados.

## Descripción general

A diferencia de `csv-profiler` (que asume un tabular limpio y usa `pandas`
directo), esta skill usa `openpyxl` en modo `read_only` para inspeccionar la
estructura del workbook **antes** de cargar el dataframe. La fase de detección
es la que aporta valor: hoja principal, fila de header, merged cells
relevantes. Recién después se carga el dataframe con `pandas.read_excel` con
los parámetros correctos (`sheet_name=`, `header=`).

`xlrd` se usa solo para archivos legacy `.xls` (formato pre-2007).

## Cuándo usar

- Primer encuentro con un `.xlsx` o `.xls` corporativo.
- El archivo tiene merged cells, logos, headers en fila 3-7, o múltiples
  hojas donde solo una tiene datos.
- Antes de cargar la skill `pandas-cleaning`.
- Cuando `pd.read_excel(path)` falla con errores crípticos ("passed
  values and the header argument") o devuelve un dataframe malformado.

No **usar** cuando:

- El archivo es CSV/Parquet → `csv-profiler` (más rápido, sin overhead de
  detección).
- El archivo Excel está limpio (header en fila 1, sin merged cells,
  columnas obvias) → `csv-profiler` también funciona; `excel-profiler` es
  overhead innecesario en ese caso. Regla: si el usuario dice "es un Excel
  simple", arrancar con `csv-profiler`.
- El archivo tiene macros (`.xlsm`) que se quieren ejecutar → fuera de
  alcance.
- El archivo está password-protected → fuera de alcance para v1.

## Flujo de trabajo

### 1. Detección del tipo y carga estructural

```python
import openpyxl
from pathlib import Path

path = Path("<input_path>")
ext = path.suffix.lower()

if ext == ".xlsx":
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
elif ext == ".xls":
    # xlrd solo lee .xls legacy — no usa openpyxl
    import xlrd
    book = xlrd.open_workbook(str(path), on_demand=True)
    sheets_info = [(name, book.sheet_by_name(name)) for name in book.sheet_names()]
else:
    raise ValueError(f"Extensión no soportada: {ext}. Use .xlsx o .xls.")

# Para .xlsx, listar hojas
sheets_info = [(ws.title, ws) for ws in wb.worksheets]
```

Reportar inmediatamente: `n_hojas`, `hojas_visibles`, `hojas_ocultas`,
`tamaño_mb`.

### 2. Selección de la hoja principal (score de densidad)

```python
def detect_sheet_with_data(sheets_info, sample_rows=50) -> str:
    """Elige la hoja con mayor densidad de filas completas en el primer chunk.

    Una hoja de metadata tiene muchas celdas con 1-2 valores por fila (texto
    descriptivo). Una hoja de datos tiene filas mayormente completas con
    tipos heterogéneos. Score = promedio de completitud por fila.
    """
    best_name, best_score = None, 0.0
    scores = {}
    for name, ws in sheets_info:
        # Score = % de filas con >=3 celdas no-vacías (filas "de datos")
        rows_with_data = 0
        total_rows = 0
        for row in ws.iter_rows(min_row=1, max_row=sample_rows,
                                 values_only=True):
            total_rows += 1
            non_empty = sum(1 for c in row if c is not None and str(c).strip() != "")
            if non_empty >= 3:
                rows_with_data += 1
        score = rows_with_data / total_rows if total_rows > 0 else 0
        scores[name] = round(score, 3)
        if score > best_score and score > 0.5:
            best_name, best_score = name, score
    return best_name, scores
```

La hoja con score > 0.5 y más alto gana. Una hoja de metadata típica tiene
score bajo porque sus filas tienen 1-2 celdas con texto. Si hay empate,
tomar la primera. Reportar las 3 hojas con score más alto para que el
usuario vea el diagnóstico.

**Importante**: la detección funciona sobre un workbook cargado con
`read_only=True` (rápido, poca memoria). `merged_cells` no está disponible
en `ReadOnlyWorksheet`, así que después de detectar la hoja se debe
**recargar el workbook en modo normal** (`read_only=False`) solo para la
hoja seleccionada. Para Excels >100MB, esto último puede ser costoso en
memoria — ver Limitaciones conocidas.

### 3. Detección de la fila de headers

```python
def detect_header_row(ws, max_scan=10) -> int:
    """Encuentra la fila donde están los headers reales.

    Estrategia de 3 pases:
    1. Primero busca una fila con todos los valores siendo strings no-numéricos
       y >=3 celdas no-vacías. Esto es el caso típico de headers
       (nombres de columna).
    2. Si no encuentra, fallback a fila con tipos heterogéneos (>=3 celdas,
       mezcla de tipos) que NO esté cubierta por merged cells.
    3. Última opción: primera fila con >=3 celdas no-vacías.
    """
    merged_ranges = list(ws.merged_cells.ranges)
    merged_rows = set()
    for mr in merged_ranges:
        for row_idx in range(mr.min_row, mr.max_row + 1):
            merged_rows.add(row_idx)

    # Pase 1: fila con todos strings (típico header)
    for row_idx in range(1, max_scan + 1):
        cells = [c.value for c in ws[row_idx]]
        non_empty = [c for c in cells if c is not None and str(c).strip() != ""]
        if len(non_empty) >= 3 and row_idx not in merged_rows:
            # ¿Todos los valores son strings no-numéricos?
            all_stringy = all(
                isinstance(c, str)
                and not c.replace(".", "").replace("-", "").isdigit()
                for c in non_empty
            )
            if all_stringy:
                return row_idx

    # Pase 2: fallback — fila con tipos heterogéneos
    for row_idx in range(1, max_scan + 1):
        cells = [c.value for c in ws[row_idx]]
        non_empty = [c for c in cells if c is not None and str(c).strip() != ""]
        if len(non_empty) >= 3 and row_idx not in merged_rows:
            types = {type(c).__name__ for c in non_empty}
            if len(types) >= 2:
                return row_idx

    # Pase 3: última opción — primera fila con >=3 no-vacías
    for row_idx in range(1, max_scan + 1):
        cells = [c.value for c in ws[row_idx]]
        non_empty = [c for c in cells if c is not None and str(c).strip() != ""]
        if len(non_empty) >= 3:
            return row_idx
    return 1
```

Devuelve el índice 1-based de la fila donde están los headers. Las filas
anteriores se reportan como "metadata previa" en el output.

### 4. Detección de merged cells relevantes

```python
def merged_cells_in_columns(ws, header_row, n_cols) -> list[dict]:
    """Reporta merged cells que afectan a columnas de datos."""
    relevant = []
    for mr in ws.merged_cells.ranges:
        # Solo merged que empiezan antes del header row y se extienden a columnas de datos
        if mr.min_row < header_row and mr.max_col <= n_cols:
            relevant.append({
                "range": str(mr),
                "value": ws.cell(mr.min_row, mr.min_col).value,
                "spans_rows": mr.max_row - mr.min_row + 1,
                "spans_cols": mr.max_col - mr.min_col + 1,
            })
    return relevant
```

### 5. Carga del dataframe con los parámetros correctos

```python
import pandas as pd

# Header_row de openpyxl es 1-based; pandas read_excel es 0-based
df = pd.read_excel(
    path,
    sheet_name=detected_sheet,
    header=detected_header_row - 1,
    skiprows=detected_header_row - 1,  # saltar filas de metadata previa
)
```

Ahora `df` tiene headers limpios y los tipos inferidos por pandas.

### 6. Perfil por columna (igual que `csv-profiler`)

Reusar el mismo algoritmo de `csv-profiler` pasos 2-3 (normalización de
nulos + perfil por columna con min/max/media/mediana/std para numéricas,
top-5 para categóricas).

### 7. Señales de alerta específicas de Excel

Además de las señales estándar de `csv-profiler`, marcar:

- **merged cells en metadata previa**: reportar su valor (útil para
  entender qué dice la portada).
- **columnas con dtype 'object' que son mayormente numéricas**: típico
  de Excel cuando hay totales al final mal formateados o caracteres
  mezclados.
- **fila con 'Total' o 'TOTAL' al final**: reportar su posición y la
  columna donde está el total (suele distorsionar agregaciones si no se
  filtra).
- **filas completamente vacías entre datos**: reportar gaps (suelen
  indicar subtotales o secciones).

### 8. Salida como markdown

```python
out_path = path.with_name(path.stem + "_profile.md")

with open(out_path, "w") as f:
    f.write(f"# Perfil: {path.name}\n\n")
    f.write("## Metadata del workbook\n\n")
    f.write(f"- Hojas: {n_hojas}\n- Hoja detectada con datos: {detected_sheet}\n")
    f.write(f"- Fila de headers detectada: {detected_header_row}\n")
    f.write(f"- Tamaño: {size_mb:.2f} MB\n\n")

    f.write("## Metadata previa al header\n\n")
    for row_idx in range(1, detected_header_row):
        cells = [(c.coordinate, c.value) for c in ws[row_idx] if c.value is not None]
        if cells:
            f.write(f"- Fila {row_idx}: {cells}\n")

    f.write("\n## Merged cells relevantes\n\n")
    for mr in merged_relevant:
        f.write(f"- `{mr['range']}`: {mr['value']!r}\n")

    f.write("\n## Perfil por columna\n\n")
    f.write(profile_df.to_markdown(index=False))

    f.write("\n\n## Tabla completa\n\n")
    f.write(f"- filas: {len(df)}\n- columnas: {df.shape[1]}\n")
    f.write(f"- duplicados: {df.duplicated().sum()}\n")
    f.write(f"- memoria: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB\n")

    f.write("\n## Señales de alerta\n\n")
    for alert in alerts:
        f.write(f"- ⚠️ {alert}\n")
```

## Recetas iniciales (snippets pre-aprobados)

- `detect_sheet_with_data(sheets_info, sample_rows=50) -> str`
- `detect_header_row(ws, max_scan=10) -> int`
- `merged_cells_in_columns(ws, header_row, n_cols) -> list[dict]`
- `profile_excel_column(ws, col_idx, header_row) -> dict`
- `find_total_rows(df) -> list[int]` — filas con "Total" en alguna columna
- `load_excel_with_detection(path) -> tuple[pd.DataFrame, dict]` — la receta
  completa end-to-end que ejecuta los pasos 1-5

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "El header está en la fila 1, uso `csv-profiler`." | Si la fila 1 tiene merged cells o metadata, `pd.read_excel` carga eso como headers y todo falla downstream. Mejor detectar explícitamente. |
| "Skip las primeras 3 filas con `skiprows=3`." | Frágil: si el archivo cambia de formato, rompe. La detección automática es robusta a cambios. |
| "Le digo al usuario que limpie el Excel a mano primero." | El usuario no va a hacerlo. El 80% de los Excels corporativos vienen así. El sistema tiene que adaptarse. |
| "Uso `xlrd` para todo." | `xlrd >= 2.0` solo lee `.xls`. Para `.xlsx` (el 95% de los casos) hay que usar `openpyxl`. |
| "Cargo todas las hojas y elijo después." | Desperdicia memoria y vuelve el reporte ilegible. Mejor elegir primero. |

## Señales de alerta

- Más del 30% de nulos en cualquier columna nombrada como "clave" o "target".
- Dtypes mezclados en la misma columna (típico de totales mal formateados).
- Fila con "Total" / "TOTAL" / "Subtotal" en alguna columna — distorsiona
  agregaciones si no se filtra.
- Merged cells que cubren más de 3 filas en metadata previa — indica que
  el Excel tiene un "header report" formal (común en finanzas).
- Hojas con score < 0.1 — probablemente son metadata, no datos.
- Memoria > 500 MB — sugerir muestreo antes de `pandas-cleaning`.
- Archivo `.xls` legacy — avisar que `openpyxl` no lo lee, hay que usar
  `xlrd`.

## Verificación

- [ ] Se detectó correctamente la hoja con datos (vs. hojas de portada).
- [ ] Se detectó correctamente la fila de headers (típicamente fila 3-7).
- [ ] Los merged cells se listan con su valor y rango.
- [ ] El dataframe cargado con `pd.read_excel(path, header=detected_row-1)`
      tiene headers limpios.
- [ ] El perfil por columna incluye todas las columnas (no solo numéricas).
- [ ] Las señales de alerta están listadas en una sección separada.
- [ ] La sección "metadata previa al header" muestra qué había antes del
      header (útil para entender el contexto).
- [ ] El archivo de origen **no** fue modificado.
- [ ] El reporte markdown se guardó como `<input_basename>_profile.md`.

## Dependencias

- `openpyxl >= 3.0` — para `.xlsx`
- `xlrd >= 2.0` — para `.xls` legacy
- `pandas >= 1.5` — para carga final y perfil

Ambas como `peerDependencies` opcionales (se instalan solo si el usuario
usa Excel; `csv-profiler` sigue funcionando sin ellas).

## Limitaciones conocidas (v1)

- **No lee fórmulas**: solo valores (los Excels con fórmulas se leen con
  `data_only=True`, lo que significa que muestra el último valor
  cacheado). Si el usuario necesita auditar fórmulas, queda como
  follow-up.
- **No soporta password**: archivos protegidos fallan con error críptico
  de openpyxl. Documentar workaround.
- **Streaming limitado**: archivos >100MB pueden dar problemas de memoria
  aunque `read_only=True`. Sugerir muestreo o procesar por hojas.
- **Más de 50 hojas**: warning, no error. Solo se reportan las 3 mejores.
- **Sin detección de tablas dinámicas**: si el Excel tiene pivot tables,
  openpyxl las trata como rangos normales y la detección puede
  confundirlas con metadata.