# docs/

Documentación de diseño del toolkit `data-analytics-agents`.

## Estructura

- `adr/` — Architecture Decision Records. Decisiones de arquitectura
  transversales al toolkit (no por skill individual).
- `prd/` — Product Requirements Documents. Una página por skill o
  feature nueva, con user story, scope in/out, workflow, recetas y
  criterios de "listo".

## Convención

- **ADR primero, PRDs después.** Si una decisión toca más de una skill
  o cambia la arquitectura del toolkit, va como ADR. Si es scope de
  una sola skill, va como PRD.
- **Status explícito**: Draft / Accepted / Superseded. Accepted lleva
  fecha de aceptación.
- **Cross-refs**: cada PRD apunta al ADR relacionado. Cada ADR lista
  los PRDs asociados.
- **Sin copy-paste del código**. Las specs describen QUÉ y POR QUÉ;
  el código vive en `skills/<name>/` y `agents/<name>.md`.

## Índice actual

### ADRs

- [001-portable-day1](adr/001-portable-day1.md) — Extender el toolkit
  para uso profesional día 1: excel-profiler + sql-cloud-warehouse +
  report-export. Aceptado 2026-09-14.

### PRDs

- [excel-profiler](prd/excel-profiler.md) — Perfilado de Excel sucio.
- [sql-cloud-warehouse](prd/sql-cloud-warehouse.md) — Soporte para
  Snowflake, BigQuery, Redshift.
- [report-export](prd/report-export.md) — Export de reportes a PDF,
  PPT y HTML standalone.