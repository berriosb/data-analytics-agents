# ADR-001 — Extender el toolkit para uso profesional día 1

> Propósito: Capturar las decisiones arquitectónicas para agregar `excel-profiler`,
> `sql-cloud-warehouse` y `report-export` al toolkit, derivadas del análisis del
> video BYOA (Bring Your Own Agents) y del gap real que existe entre el toolkit
> actual y un data analyst llegando a una pega nueva el lunes.

- **Status:** Aceptado (2026-09-14)
- **Contexto:** toolkit open-source `data-analytics-agents` con 5 personas + 13 skills, listo para uso en CLI pero con gaps concretos para trabajo corporativo real.

## Contexto

El toolkit actual cubre el ciclo CSV/Parquet/Excel-local + sqlite/postgres/mysql/duckdb
+ modelado supervisado + reporting con Plotly. Hay tres brechas para que funcione
como sistema de trabajo del día 1 en una pega de data analyst:

1. **Excel "sucio"** — el `csv-profiler` apunta a CSV/Parquet/Excel limpios. En pega
   real, el 60% de los datos viven en Excel con merged cells, footnotes, headers
   en fila 3-7, y sheets mezclando datos con metadata.
2. **Cloud warehouses** — el `sql-analyst` cubre sqlite/postgres/mysql/duckdb. El
   mercado enterprise chileno (retail, bancos, telcos, fintech) usa Snowflake,
   BigQuery y Redshift. Sin soporte, el sistema no carga donde se gana la plata.
3. **Export ejecutivo** — el `reporting-analyst` produce gráficos Plotly + texto en
   notebook. Falta exportar a PDF/PPT/HTML standalone, listo para mandar al
   stakeholder sin que tenga que correr nada.

Estas tres skills existen para que el sistema **llegue y produzca el día 1**, no
para展示.

## Decisiones arquitectónicas

### 1. Stack de cada skill nueva

| Skill | Librería base | Por qué |
|---|---|---|
| `excel-profiler` | `openpyxl` + `pandas` + `xlrd` (legacy `.xls`) | openpyxl lee sheets con merged cells; pandas consolida. xlrd solo para `.xls` legacy. Sin dependencias cloud. |
| `sql-cloud-warehouse` | `sqlalchemy` + driver específico (snowflake-connector-python, google-cloud-bigquery, redshift-connector) | SQLAlchemy abstrae dialectos. Drivers oficiales por warehouse. Sin reinventar la rueda. |
| `report-export` | `kaleido` (Plotly→PNG/PDF) + `python-pptx` (PPT) + `weasyprint` o `pdfkit` (PDF narrado) | Kaleido ya es el exportador oficial de Plotly. python-pptx es estándar para PPT. Weasyprint para HTML→PDF con CSS. |

### 2. Formato de skill — mismo template que las 13 existentes

Las tres siguen el template de 6 secciones:
- Descripción general
- Cuándo usar (con trigger phrases)
- Flujo de trabajo (paso a paso)
- Justificaciones comunes
- Señales de alerta
- Verificación

Sin frontmatter especial. Sin configuración nueva en `bin/install.js` — los skills
se symlinkean por nombre desde `skills/<name>/SKILL.md` y los CLIs los auto-descubren.

### 3. Personas que referencian estas skills

- `excel-profiler`: lo carga `data-explorer` **antes** de `csv-profiler` cuando el
  archivo es `.xlsx`/`.xls`. `csv-profiler` sigue siendo el fallback para CSV/Parquet.
- `sql-cloud-warehouse`: lo carga `sql-analyst` **antes** de `sql-query-helper`
  cuando el target es Snowflake/BigQuery/Redshift. `schema-mapper` queda igual.
- `report-export`: lo carga `reporting-analyst` **al final**, después de
  `insight-synthesis`, para empaquetar el reporte ejecutivo.

### 4. Multi-CLI compatibility — sin cambios

Las tres skills son markdown + snippets Python. Se distribuyen via el patrón
existente: el usuario corre `npx data-analytics-agents install --all` y los
symlinks aparecen en `.opencode/skills/`, `.claude/skills/`, `.agents/skills/`
y en el plugin de Antigravity. No requiere tocar `bin/install.js`.

### 5. Snippets pre-aprobados — disciplina cerrada

Igual que las 13 skills existentes:
- **Sin `eval()` ni `df.query(<expr del usuario>)`** abierto.
- **Sin acceso a secrets en claro** — los snippets leen `os.environ` para
  credenciales; el usuario las configura vía `.env` o vault, nunca en el código.
- **Sin escritura destructiva por defecto** — `sql-cloud-warehouse` solo lee;
  si más adelante hace falta DDL, va como bloque explícito aprobado.

### 6. Distribución — sigue siendo una sola publicación npm

Las tres skills viven en `skills/<name>/SKILL.md` y se incluyen en el paquete
existente. No hay paquetes separados. El `package.json` solo bumpea la versión
(`1.x.0` → `1.(x+1).0`) y agrega las deps de runtime a `peerDependencies`
opcionales (pandas, sqlalchemy, drivers).

## Trade-offs considerados

### ¿Por qué no incluir `data-engineer` (ingesta) en este pase?

`data-engineer` cubre APIs/S3/scraping. Es **más grande** que las 3 skills de
Nivel 1 y requiere decisiones distintas (rate limiting, autenticación OAuth,
manejo de errores transitorios). Lo dejamos para ADR-002 después de validar
que Nivel 1 funciona end-to-end.

### ¿Por qué no usar Polars en vez de pandas?

Polars es más rápido pero el `csv-profiler` y `pandas-cleaning` ya están
construidos sobre pandas. Migrar todo el toolkit a Polars es un proyecto aparte
(rompe snippets, requiere reescribir 13 skills). Para las 3 nuevas, pandas es
consistente con el resto y los data analysts en pega nueva ya lo conocen.

### ¿Por qué no usar DuckDB como única opción para warehouses?

DuckDB local funciona para prototyping, pero no lee directo de Snowflake/BigQuery
sin un conector externo. Mantener DuckDB como opción del `sql-analyst` (ya está)
y agregar `sql-cloud-warehouse` para producción cloud es más honesto con la
realidad del mercado.

## Riesgos

- **Dependencias de drivers cloud pesadas**: `snowflake-connector-python` pesa
  ~50MB. Solución: declarar como `peerDependencies` opcionales; el usuario
  instala solo el driver del warehouse que usa.
- **`openpyxl` no lee Excel fórmulas, solo valores**: si el usuario quiere
  leer fórmulas para auditoría, necesita `formulas` o `xlcalculator`. Decidido:
  primera versión solo lee valores (cubre el 90% del caso). Fórmulas como
  follow-up.
- **`weasyprint` requiere GTK en Linux**: workaround con `pdfkit` (wkhtmltopdf)
  si Weasyprint falla en el entorno del usuario. Documentado en la skill.

## Relación con ADRs/PRD existentes

- `AGENTS.md` — referencia a las 3 skills nuevas (actualizar tras implementación).
- `README.md` — mención en la tabla de skills y en "Convenciones" (sin
  reescritura masiva).
- `bin/install.js` — **sin cambios**. La instalación multi-CLI ya soporta
  skills arbitrarios.
- `examples/` — agregar un Excel sucio de muestra, un script de demo de
  Snowflake/BigQuery (con credenciales fake), y un reporte exportado de ejemplo.

## PRDs asociados

- `docs/prd/excel-profiler.md`
- `docs/prd/sql-cloud-warehouse.md`
- `docs/prd/report-export.md`