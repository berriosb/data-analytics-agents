# PRD — `excel-profiler`

- **Status:** Accepted (2026-09-15)
- **Implementation:** shipped at v0.4.0 (ADR-001 era). Ver [CHANGELOG.md](../../CHANGELOG.md).
- **Owner:** CodeHak (Bastian)
- **ADR relacionado:** [001-portable-day1](../adr/001-portable-day1.md)
- **Skills relacionadas:** `csv-profiler` (queda como fallback), `pandas-cleaning` (siguiente paso)

## Goal

Que un data analyst pueda llegar el lunes con un `.xlsx` corporativo con merged
cells, headers en fila 3-7, columnas mezcladas con metadata, y obtener un
**perfil limpio en menos de 5 minutos**, listo para pasar a `pandas-cleaning`
sin tener que decidir a mano qué fila es el header ni qué columnas descartar.

## User story

> Como data analyst nuevo en una pega corporativa, recibo un Excel del equipo
> de finanzas con las ventas del trimestre. El archivo tiene 3 hojas, la hoja
> "Data" tiene merged cells arriba con el logo de la empresa y el título del
> reporte, los headers reales están en la fila 6, hay una columna "Notas" con
> texto libre mezclado con números, y la última fila tiene un total mal
> formateado. Necesito un comando que me diga: "estas son las 4 hojas, la que
> tiene datos limpios es la hoja X, los headers reales están en la fila Y,
> estas son las columnas candidatas a type-inference, estas son las que
> tienen >30% nulos y deberías dropear". Sin decidir nada yo.

## Scope in (v1)

- Archivos `.xlsx` (openpyxl) y `.xls` legacy (xlrd).
- Detección automática de la hoja con datos (vs. hojas de metadata/portada).
- Detección automática de la fila de headers (busca la primera fila con ≥3
  celdas no-vacías y tipos consistentes).
- Perfil por columna: dtype inferred, % nulos, cardinalidad, top-3 valores,
  min/max para numéricas, fecha min/max para temporales.
- Reporte de merged cells y notas en el output.
- Output en formato compatible con `pandas-cleaning` (mismo schema JSON
  que produce `csv-profiler`, extendido con `excel_metadata`).

## Scope out (v1, queda como follow-up)

- **Lectura de fórmulas**: solo valores. Si el usuario necesita auditar
  fórmulas, va como ADR-002.
- **Archivos password-protected**: sin soporte. Documentar workaround.
- **Excel con macros (.xlsm)**: sin soporte. Macros se ignoran, datos sí.
- **Más de 50 hojas**: warning, no error. Perfil parcial.
- **Streaming de archivos >100MB**: warning + sugerencia de muestreo.

## Workflow (las 6 fases de la skill)

1. **Detección**: `openpyxl.load_workbook(path, read_only=True, data_only=True)`.
   Reportar cantidad de hojas, tamaño aproximado, hojas ocultas.
2. **Selección de hoja**: para cada hoja, calcular "score de densidad" = %
   celdas no-vacías en el primer chunk (filas 1-50). La hoja con score más
   alto y >50% es la candidata. Si hay empate, tomar la primera.
3. **Detección de header**: scanear filas 1-10 buscando la primera fila con
   ≥3 celdas no-vacías, sin merged cells que la crucen, y donde las celdas
   tengan tipos heterogéneos (mezcla de string + número). Esa fila es el
   header. Las filas anteriores se reportan como "metadata previa".
4. **Perfil por columna**: sobre la hoja + header detectados, aplicar el
   mismo perfil que `csv-profiler` (dtype, nulos, cardinalidad, top-3,
   min/max). Extender con `excel_metadata`: nombre original de la hoja,
   merged cells que afectan esta columna, fila del header detectada.
5. **Señales de alerta**: marcar columnas con >30% nulos, con dtype mixto
   (números + strings), con cardinalidad 1 (constantes), con cardinalidad
   == n_filas (IDs únicos).
6. **Output**: JSON estructurado en el mismo formato que `csv-profiler`,
   más sección `excel_metadata`. También print a stdout un resumen legible.

## Recetas iniciales (snippets pre-aprobados)

- `detect_sheet_with_data(wb) -> str` — elige la hoja principal.
- `detect_header_row(ws, max_scan=10) -> int` — encuentra la fila de headers.
- `profile_xlsx_column(ws, col_idx, header_row) -> dict` — perfil por columna.
- `merged_cells_in_column(ws, col_idx) -> list[str]` — reporta merged cells.

## Verificación (criterios de "listo")

- [ ] `examples/sample_dirty_excel.xlsx` provisto: 3 hojas, header en fila 6,
  merged cells, columna con 60% nulos, columna constante, columna ID único.
- [ ] `make test-excel` ejecuta las recetas sobre el sample y verifica:
  - Detecta "Data" como hoja principal.
  - Detecta fila 6 como header.
  - Marca correctamente las columnas con alerta.
  - Output JSON parseable con `excel_metadata`.
- [ ] La skill está en `skills/excel-profiler/SKILL.md` con el template
  de 6 secciones completo.
- [ ] `AGENTS.md` actualizado: `data-explorer` carga `excel-profiler` ANTES
  de `csv-profiler` cuando el input es `.xlsx`/`.xls`.
- [ ] `bin/install.js` corre sin cambios: el skill aparece en
  `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`, plugin Agy.

## Estimación

- Specs + sample sucio: 30 min (hecho).
- Implementación SKILL.md + recetas: 2-3 horas.
- Test sample: 30 min.
- Actualización AGENTS.md/README: 15 min.

**Total: ~4 horas de código + tests.**