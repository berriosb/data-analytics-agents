# Changelog

Todos los cambios visibles para el usuario en este toolkit. El formato está
inspirado en [Keep a Changelog](https://keepachangelog.com/) y el versionado
sigue [SemVer](https://semver.org/). La fuente de verdad para el alcance de
cada release es `package.json` + los PRDs en [`docs/prd/`](docs/).

## [Unreleased]

Sin cambios pendientes. El plan para v1.x vive en "Out of scope para
v1.0" debajo.

## [1.0.0] — 2026-09-15

Primer release estable (GA). Cierra el ciclo de release acumulado
desde v0.3.0 con foco en confianza, documentación y cobertura de tests.

### Added

- **`docs/architecture.md`** — mapa mental de las 5 personas + 20 skills,
  con diagramas Mermaid de triaje/handoffs y grafo de referencia de
  skills. Cross-linked desde `AGENTS.md` y `README.md`.
- **`CHANGELOG.md`** — release notes estructuradas (formato
  Keep a Changelog + SemVer) con roadmap a v1.0 marcado al dia.
- **Unit tests sobre snippets de skills** (`make test-unit`) — 161 tests
  cubriendo los 6 skills con módulo `recetas/` (api-builder, audit-log,
  excel-formulas, report-export, sql-cloud-warehouse, sql-write). Happy
  path + edge cases + guardrails de seguridad (PII redaction, SQL
  blockers, dialecto-aware snippets).
- **`identifier_quote()` snippet** en `sql-cloud-warehouse` — devuelve
  identificadores entrecomillados segun dialecto (backticks para
  BigQuery/Databricks, comillas dobles para Snowflake/Redshift). Cierra
  el gap G4 del review de Databricks.
- **`docs/notes/databricks-coverage.md`** — review técnico del dialecto
  Databricks (Spark SQL) con inventario de cobertura + 7 gaps
  identificados + recomendaciones priorizadas.

### Changed

- **PRDs flippeados a Accepted** — los 7 PRDs (`api-builder`,
  `audit-log`, `excel-formulas`, `excel-profiler`, `report-export`,
  `sql-cloud-warehouse`, `sql-write`) pasaron de `Draft → Ready` a
  `Accepted (2026-09-15)`. Las skills existían y los ADRs estaban
  aceptados; el flip refleja el estado real.
- **`audit-log/redact.py`** — `credit_card` se matchea antes que
  `phone_cl`. Antes, un PAN de 16 dígitos terminaba redactado
  parcialmente como teléfono porque `phone_cl` ganaba primero y rompía
  el match completo del PAN. Ahora el PAN se redacta entero.
- **`sql-write/validate.py`** — `validate_sql` ahora detecta "SQL con
  solo comentarios" como vacío (`(False, "SQL sin contenido (solo
  comentarios)")`). Antes pasaba como válido silenciosamente porque el
  comment-stripping estaba dentro de `_validate_statement` que
  retornaba sin error.

### Documentation

- Cross-link de `docs/architecture.md` desde `AGENTS.md` (nueva
  sección "Mapa de la arquitectura") y desde `README.md` (nueva
  sección "Documentación adicional").
- `docs/README.md` agrega índice de arquitectura y sección de notes.
- README reorganiza la sección de "Tests" para distinguir smoke
  vs unit tests.

## [0.9.0] — 2026-09-14

### Added

- **Databricks (Spark SQL)** como warehouse soportado en
  `sql-cloud-warehouse`. Se suman a Snowflake, BigQuery y Redshift.
  Driver via `databricks-sql-connector` + `databricks-sqlalchemy`
  (peer-deps opcionales). Snippets dialecto-aware para `DATE_TRUNC`,
  `IFF` y `TRY_CAST` agregados a la skill.

## [0.8.1] — 2026-09-14

### Fixed

- Sincronización de instaladores a las 20 skills (algunos symlinks
  apuntaban a skills que se renombraron durante el ciclo v0.5.0–
  v0.8.0). Smoke tests cubren ahora la suite completa unificada
  via `make test`.

## [0.8.0] — 2026-09-14

### Added

- **`audit-log`** — log transversal append-only (JSONL o SQLite vía
  env var) que registra cada operación contra DB: quién, cuándo, qué
  query (preview), duración, filas afectadas. Redacción automática
  de PII (emails, RUTs chilenos, teléfonos CL, tarjetas). Lo carga
  cualquier skill que toque DB — `sql-analyst`, `sql-cloud-warehouse`,
  `sql-write`. ADR-002.

## [0.7.0] — 2026-09-14

### Added

- **`sql-write`** — persistencia segura de resultados en DB con
  guardrails explícitos. Modo conservador permite `CREATE TABLE IF
  NOT EXISTS` + `INSERT`; bloquea `DROP`/`UPDATE`/`DELETE`/`TRUNCATE`/
  `ALTER`/`GRANT`/`REVOKE`. Dry-run obligatorio + doble confirmación
  antes de ejecutar. Integración con `audit-log`. ADR-002.

## [0.6.0] — 2026-09-14

### Added

- **`excel-formulas`** — extracción y clasificación de fórmulas Excel
  a partir de un workbook (texto crudo de la fórmula, valor cached,
  categoría funcional: aggregate / lookup / logical / text / date /
  financial / math). Detecta fórmulas volátiles (`NOW`, `RAND`,
  `OFFSET`, `INDIRECT`) y errores (`#REF!`, `#DIV/0!`, `#NAME?`).
  Análisis avanzado de dependencias opcional vía librería `formulas`.
  ADR-002.

## [0.5.0] — 2026-09-14

### Added

- **`api-builder`** — convierte una función Python de análisis o
  scoring en una API REST production-ready (FastAPI + Pydantic +
  uvicorn). Genera `app.py`, `models.py`, `requirements.txt`,
  `Dockerfile`, `README.md` y `tests/test_app.py`. Auth opcional via
  API key en header. Lo carga `reporting-analyst` como paso opcional
  al final del flujo, cuando el stakeholder quiere consumir el
  análisis como servicio. ADR-002.

## [0.4.0] — 2026-09-14

### Added

- **`sql-cloud-warehouse`** — conexión e introspección a Snowflake,
  BigQuery y Redshift via SQLAlchemy + drivers oficiales (peer-deps
  opcionales). Snippets dialecto-aware: `DATE_TRUNC` (argumentos en
  orden distinto por warehouse), `IFF`/`IF`/`CASE`, `SAFE_CAST`/
  `TRY_CAST`, backticks opcionales vs obligatorios. Solo lectura
  (SELECT únicamente). ADR-001.
- **`excel-profiler`** — perfilado de Excel corporativo "sucio".
  Detecta automáticamente la hoja con datos (vs hojas de
  portada/metadata), la fila real de headers (frecuente en fila 3-7
  entre merged cells), y reporta merged cells, columnas con >30%
  nulos, dtypes mezclados y columnas constantes. Output en formato
  compatible con `csv-profiler`. ADR-001.

## [0.3.0] — 2026-09-14

### Added

- **`report-export`** — export de reportes ejecutivos a PDF
  (WeasyPrint con fallback a pdfkit si GTK no está disponible),
  PPTX (python-pptx, un gráfico por slide + slide de insights) o
  HTML standalone (base64 inline, abrible en cualquier browser sin
  dependencias externas). Lo carga `reporting-analyst` al final,
  después de `insight-synthesis`. ADR-001.

## Notas de versionado

- **Minor (1.x.0)** cuando se agrega una skill nueva o un agente
  nuevo, o cuando cambia la forma de orquestación entre agentes.
- **Patch (1.x.y)** cuando se arregla un bug, se mejora un snippet
  pre-aprobado, o se sincroniza documentación.
- **Major (x.0.0)** reservado para cambios incompatibles en el
  frontmatter de las skills o en el contrato del instalador
  (`bin/install.js`). El primer major fue v1.0.0.

## Cómo actualizar

```bash
# En el proyecto destino:
npm update data-analytics-agents
npx data-analytics-agents install --all   # idempotente
```

Los symlinks en `.opencode/`, `.claude/` y `.agents/` siguen
apuntando al mismo `node_modules/data-analytics-agents/`; las
ediciones y updates se reflejan al instante, no hace falta
re-instalar.

## Out of scope para v1.0 (planeado para v1.x)

- `data-engineer` (ingesta APIs / S3 / scraping). ADR-003 cuando haya
  demanda concreta. Es **más grande** que las 3 skills de v0.4.0 juntas
  (rate limiting, OAuth, retries) y amerita su propio pase.
- `make doctor` (preflight de Node, Python y peer-deps opcionales).
  Hoy `make list` muestra estado de instalación; `make doctor`
  agregaría verificación de versiones y depeer-deps que el usuario
  tiene cargados.
- AutoML / hyperparameter search. Fuera de alcance de `ml-modeler`
  (mencionado en [README](README.md) sección "Fuera de alcance").
- Modo "full" de `sql-write` (DROP/UPDATE/DELETE con rollback script).
  El modo conservador cubre el 90% del caso; el resto necesita
  audit log + dry-run + transactional DDL que es otro ADR.
- Soporte OAuth2 / service accounts para `sql-cloud-warehouse`. Hoy
  son credenciales estáticas en env.
- **QUALIFY clause** snippet para Databricks (gap G2 del review).
  Bajo esfuerzo (snippet + 2 tests), pero no bloqueante.
- **PIVOT / STRING_AGG / date_add** snippets. Divergencia real entre
  dialectos hace que un helper "seguro" no exista — mejor dejarlos
  como patrones de `sql-query-helper` cuando se necesiten.
- **Unit tests sobre los 14 skills sin `recetas/`**
  (csv-profiler, pandas-cleaning, viz-patterns, statistical-testing,
  time-series-patterns, feature-engineering, ml-modeling,
  model-evaluation, schema-mapper, sql-query-helper,
  using-data-analytics-agents, insight-synthesis, query-validation,
  excel-profiler). Requiere extraer los snippets de markdown a
  código Python importable (ADR aparte) antes de poder testearlos.
