# PRD — `excel-formulas`

- **Status:** Accepted (2026-09-15)
- **Implementation:** shipped at v0.6.0. Ver [CHANGELOG.md](../../CHANGELOG.md).
- **Owner:** CodeHak (Bastian)
- **ADR relacionado:** [002-end-to-end-delivery](../adr/002-end-to-end-delivery.md)
- **Skills relacionadas:** `excel-profiler` (base), `data-explorer` (carga esta solo si el usuario pide auditar fórmulas)

## Goal

Que un data analyst pueda abrir un Excel corporativo y **ver las fórmulas
que están detrás de los números**, no solo los valores. Esto es crítico
para auditoría financiera, validación de modelos, y para entender cómo
el equipo anterior construyó un reporte que estás heredando.

## User story

> Como data analyst en una fintech, me pasan un Excel de "margen por
> cliente Q2 2026" con columnas `revenue`, `costs`, `margin_pct`,
> `margin_clp`. Los números no cuadran con mi modelo. Necesito ver
> qué fórmula está en cada celda para entender si es un cálculo
> correcto o un workaround histórico. Sin tener que abrir cada celda
> en Excel y clickear "Show Formulas".

## Scope in (v1)

- **Inputs**: ruta a un Excel `.xlsx` (openpyxl ya soporta legacy `.xls`
  via xlrd; el path ya está implementado en `excel-profiler`).
- **Outputs**:
  - **Fórmula textual** de cada celda (`=SUM(A1:A10)+B2*0.19`)
  - **Valor cached** de la celda (lo que muestra Excel al abrir)
  - **Análisis de dependencias** (qué celdas usa la fórmula y qué
    celdas la usan): opcional via `formulas` library
  - **Reporte markdown** por hoja: tabla con columna, fila, fórmula,
    valor, tipo
  - **Senalización de fórmulas complejas**: arrays (CSE), volatile
    (NOW, RAND), shared formulas, errores (#REF!, #DIV/0!)
- **Solo lectura**: nunca modifica el archivo de origen
- **Funciona sin `formulas` instalado**: el caso 80% (mostrar fórmula
  textual) usa openpyxl. La instalación de `formulas` es opcional para
  análisis avanzado de dependencias.

## Scope out (v1, queda como follow-up)

- **Modificar fórmulas en el archivo**: fuera de scope. La skill es
  read-only.
- **Recalcular fórmulas**: openpyxl lee el valor cached que guardó Excel
  al guardar; si el archivo fue editado fuera de Excel, el valor cached
  puede estar desactualizado. Para recalcular, el usuario debe abrir
  Excel o usar `xlcalculator` (follow-up).
- **Volatiles como NOW()/TODAY() evaluadas al momento del parseo**:
  fuera de scope. Documentamos que esas fórmulas no son confiables para
  auditoría temporal.
- **Macros VBA**: fuera de scope. Si el Excel tiene macros, se ignoran.
- **Fórmulas XLOOKUP/LET/LAMBDA** (Excel 365+): el parser de `formulas`
  tiene cobertura parcial. Documentamos el gap.

## Workflow (las 6 fases de la skill)

1. **Detectar el archivo**: `openpyxl.load_workbook(path,
   read_only=True, data_only=False)` — `data_only=False` es crítico:
   hace que `cell.value` devuelva la fórmula, no el valor cached.
2. **Para cada hoja con datos**, recorrer todas las celdas que tengan
   fórmula (`cell.data_type == 'f'`).
3. **Clasificar la fórmula**:
   - Texto crudo: `=SUM(A1:A10)+B2*0.19`
   - Tipo de fórmula (heurística por prefijo): aggregate (SUM/AVERAGE),
     lookup (VLOOKUP/INDEX/MATCH), logical (IF/AND/OR), text (CONCAT),
     date (NOW/TODAY), error, other
   - Volatile (NOW, RAND, OFFSET, INDIRECT)
   - Shared formula o array formula
4. **Detectar errores**: si el valor cached es un string que empieza
   con `#` (`#REF!`, `#DIV/0!`, `#NAME?`), marcar como error.
5. **Análisis de dependencias** (opcional, requiere `formulas`):
   - Qué celdas referencia la fórmula (parseando el AST)
   - Qué celdas dependen de esta (búsqueda reversa)
6. **Reporte markdown** por hoja + resumen agregado (totales por tipo,
   lista de errores, lista de fórmulas volátiles).

## Recetas iniciales (snippets pre-aprobados)

- `extract_formulas(path, sheet_name=None) -> list[dict]` — extrae
  todas las fórmulas del workbook (o de una hoja específica)
- `classify_formula(formula_str) -> dict` — clasifica por tipo y
  detecta volatile/error
- `analyze_dependencies(path, cell_ref) -> dict` — opcional, requiere
  `formulas` instalado
- `build_report(workbook_path, output_path=None) -> Path` — genera
  el reporte markdown

## Verificación (criterios de "listo")

- [ ] `examples/excel_formulas_sample/` con un Excel que tenga:
  - Al menos 1 fórmula aggregate (SUM, AVERAGE)
  - 1 fórmula lookup (VLOOKUP o INDEX-MATCH)
  - 1 fórmula logical (IF)
  - 1 error (#REF! o #DIV/0!)
  - 1 fórmula volatile (NOW())
- [ ] `make test-excel-formulas` ejecuta el demo y valida que el
  reporte tenga las clasificaciones correctas.
- [ ] La skill está en `skills/excel-formulas/SKILL.md` con el
  template de 6 secciones completo.
- [ ] `AGENTS.md` actualizado: `data-explorer` carga `excel-formulas`
  SOLO si el usuario pide auditar fórmulas (no por defecto).
- [ ] `package.json`: `formulas` declarada como peerDep opcional.
- [ ] `bin/install.js` corre sin cambios.

## Estimación

- Specs + sample: 30 min (hecho).
- Implementación SKILL.md + recetas: 1.5-2 horas.
- Demo + tests: 1 hora.
- Actualización AGENTS.md/package.json: 30 min.

**Total: ~3-4 horas de código + tests.**