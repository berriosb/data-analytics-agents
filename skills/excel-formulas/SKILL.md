---
name: excel-formulas
description: Audita las formulas de un Excel corporativo (.xlsx/.xls) — muestra la formula textual, valor cached, categoria (aggregate/lookup/logical/text/date/financial/math), y senala volatiles (NOW/RAND/OFFSET/INDIRECT) y errores (#REF!/#DIV/0!/etc.). Usese SOLO cuando el usuario pide auditar formulas (no por default) — data-explorer carga esta skill despues de excel-profiler si la peticion lo amerita. Funciona con openpyxl puro (ya instalado para excel-profiler); la libreria 'formulas' es peerDep opcional para analisis avanzado de dependencias que no esta en v1.
---

# Excel Formulas

Extrae y clasifica las fórmulas de un Excel corporativo para auditoría.
Complementa a `excel-profiler` (que detecta estructura) agregando
**qué cálculo** está detrás de cada número.

## Descripción general

A diferencia de `excel-profiler` (que mira la estructura: hoja, headers,
merged cells), esta skill mira el **contenido calculado**:

- Fórmula textual (`=SUM(A1:A10)+B2*0.19`)
- Valor cached (lo que Excel guardó al guardar; puede estar desactualizado)
- Categoría (aggregate, lookup, logical, text, date, financial, math, info)
- Flags: volatile (NOW, RAND, OFFSET, INDIRECT), array formula, errores

Usa **openpyxl puro** (ya peerDep) — funciona sin instalar nada extra.
La librería `formulas` está planeada como peerDep opcional para análisis
avanzado de dependencias entre celdas, pero **no es necesaria en v1**.

## Cuándo usar

Invocar esta skill cuando el pedido matchee con alguno de:

- "Auditeme este Excel y mostrame las fórmulas detrás de los números."
- "¿Qué fórmulas usa este reporte de margen?"
- "Hay errores ocultos en este Excel?"
- "Necesito ver qué celdas dependen de cuáles para refactorizar."

**No** invocar cuando:

- El usuario solo quiere ver estructura (hojas, headers) → `excel-profiler`.
- El usuario quiere ejecutar las fórmulas y obtener resultados → fuera de
  scope v1 (openpyxl no evalúa; eso requiere `formulas` o `xlcalculator`
  o abrir Excel).
- El usuario quiere modificar fórmulas → fuera de scope. Esta skill es
  **read-only**.

## Flujo de trabajo

1. **Validar el archivo**: recibir `--workbook-path`, `--output-path`
   (opcional), `--sheet-name` (opcional). Verificar que existe.
2. **Cargar el workbook DOS veces** con openpyxl:
   - `data_only=False` → devuelve la fórmula textual en `cell.value`
   - `data_only=True` → devuelve el valor cached
3. **Recorrer celdas** con `data_type='f'` (formula) y extraer:
   - Sheet, cell coordinate, row, column
   - Fórmula textual (sin el `=` al inicio)
   - Valor cached (puede ser None si Excel no lo calculó aún)
   - Flag `value_is_error` si el cached value es un error string
4. **Clasificar** cada fórmula con heurística por nombre de función:
   - aggregate (SUM, AVERAGE, COUNT, ...) — el comodín
   - financial (NPV, IRR, PMT)
   - lookup (VLOOKUP, INDEX, MATCH, OFFSET)
   - text (CONCAT, LEFT, MID, ...)
   - date (NOW, TODAY, YEAR, ...)
   - math (ABS, ROUND, SQRT, ...)
   - logical (IF, AND, OR, IFERROR)
   - info (ISBLANK, ISNUMBER, TYPE)
   - other / error
   **Más específica gana**: si hay `ROUND(SUM(...))` se clasifica como math.
5. **Detectar flags especiales**:
   - **Volatile**: usa NOW, TODAY, RAND, OFFSET, INDIRECT, INFO, CELL
   - **Error**: contiene `#REF!`, `#DIV/0!`, `#N/A`, etc.
   - **Complejidad**: simple (≤1 func, ≤1 profundidad), medium, complex
6. **Generar reporte markdown** con:
   - Metadata del workbook
   - Resumen por categoría (% del total)
   - Lista de errores detectados
   - Lista de fórmulas volátiles con warning
   - Tabla detallada por hoja (celda | fórmula | valor | categoría | flags)

## Recetas pre-aprobadas (importables)

```python
import sys
sys.path.insert(0, "ruta/al/repo")
from skills_loader import load_skill_packages
load_skill_packages("skills")

from excel_formulas.recetas import (
    extract_formulas,                # -> list[dict]
    classify_formula,                # -> dict (category, functions_used, is_volatile, ...)
    build_report,                    # -> Path (markdown generado)
    ExcelFormulaError,
)
```

Las recetas son funciones puras excepto `build_report` (que escribe a disco).

## CLI rápido (uso desde el agente o terminal)

```bash
# 1. Generar sample (si no tenés un Excel a mano)
python examples/excel_formulas_sample/generate_sample.py

# 2. Demo end-to-end (extrae + clasifica + genera reporte)
python examples/excel_formulas_sample/demo_offline.py

# 3. Ad-hoc contra tu propio Excel
python -c "
import sys; sys.path.insert(0, '.')
from skills_loader import load_skill_packages
load_skill_packages('skills')
from excel_formulas.recetas import build_report
out = build_report('mi_excel.xlsx', 'reports/audit.md')
print('Reporte:', out)
"
```

## Diferencias con `excel-profiler`

| Skill | Qué hace | Cuándo |
|---|---|---|
| `excel-profiler` | Estructura: hoja con datos, fila de headers, merged cells, alertas de nulos/constantes | Primer encuentro con un Excel "sucio" |
| `excel-formulas` (esta) | Contenido: fórmula textual, valor cached, categoría, volatile, errores | Auditoría de cálculos o entender cómo se construyó un reporte |

Si el usuario solo quiere perfilar la estructura → `excel-profiler`. Si
además pide "ver las fórmulas" o "auditar" → cargar esta skill después.

## Justificaciones comunes

- **Por qué openpyxl y no `formulas` por defecto?** Porque openpyxl lee
  la fórmula textual (que es lo que importa para auditoría) sin
  dependencias extra. `formulas` parsea el AST y permite análisis de
  dependencias, pero es pesada (~30MB) y agrega complejidad innecesaria
  para el caso80%.
- **Por qué "más específica gana" en la clasificación?** Porque una
  fórmula como `=ROUND(SUM(A:A), 2)` es **principalmente** math (lo
  que el usuario ve como cálculo numérico). Aggregate aparece como
  secundario. El reporte prioriza la categoría más útil para entender
  la fórmula.
- **Por qué leer `data_only=False` para fórmulas y `data_only=True`
  para valores?** Porque openpyxl tiene un solo modo por workbook.
  Necesitamos las dos cargas para tener ambos en una sola pasada.

## Señales de alerta

- **Cached value es None**: openpyxl no ejecutó la fórmula. El archivo
  fue guardado por otra herramienta que no calcula (e.g. Python puro).
  El usuario debe abrir Excel y guardar de nuevo para que se cachee.
- **Cached value es `#REF!` o similar**: la fórmula referencia celdas
  que ya no existen. El reporte lo marca automáticamente.
- **NOW() / TODAY() / RAND()**: el valor cached no es representativo
  del cálculo actual (estas funciones son volatile). Warning explícito
  en la sección dedicada.
- **Archivo con macros (.xlsm)**: openpyxl puede abrirlos pero las
  macros no se ejecutan. Las fórmulas en sheets con macros sí se
  extraen; el comportamiento es el mismo que sin macros.
- **Fórmulas XLOOKUP/LET/LAMBDA**: son funciones Excel 365+. Si tu
  versión de openpyxl es <3.1, no se extraen correctamente. La skill
  emite warning si `cell.data_type != 'f'` para celdas que parecen tener
  fórmula.

## Verificación

Criterios de "listo" (ver `docs/prd/excel-formulas.md`):

- [x] `examples/excel_formulas_sample/` con un Excel que tiene:
  - Aggregate (SUM, AVERAGE) ✓
  - Lookup (VLOOKUP) ✓
  - Logical (IF, IFERROR) ✓
  - Math (ROUND, ABS) ✓
  - Date volatile (NOW) ✓
  - Compound (IF + ROUND + SUM) ✓
- [x] `make test-excel-formulas` ejecuta el demo y valida:
  - 13 fórmulas extraídas
  - Classifier pasa 6/6 casos representativos
  - Reporte markdown contiene secciones: metadata, resumen por categoría,
    volátiles, detalle por hoja
- [x] La skill está en `skills/excel-formulas/SKILL.md` con el template
      de 6 secciones completo.
- [x] `AGENTS.md` actualizado: `data-explorer` carga `excel-formulas`
      SOLO si el usuario pide auditar fórmulas.
- [x] `package.json`: `formulas` declarada como peerDep opcional.

## Dependencias

- **openpyxl** >= 3.1 — peerDep opcional (ya estaba para excel-profiler)
- **formulas** >= 1.2 — peerDep opcional (para análisis avanzado de
  dependencias, NO requerido en v1)
- **xlcalculator** >= 0.5 — peerDep opcional (alternativa a `formulas`
  para evaluar fórmulas, NO requerido en v1)

Sin instalar nada extra, la skill funciona con openpyxl y cubre el
caso 80% (auditoría con fórmula textual).