# Changelog

Todos los cambios visibles para el usuario en este toolkit. El formato está
inspirado en [Keep a Changelog](https://keepachangelog.com/) y el versionado
sigue [SemVer](https://semver.org/). La fuente de verdad para el alcance de
cada release es `package.json` + los PRDs en [`docs/prd/`](docs/).

## [Unreleased]

### Planeado para v1.0.0

Criterios para promover v0.9.x a v1.0.0 (cuando estén todos marcados):

- [ ] **Unit tests sobre snippets de skills** (no solo smoke tests de
      examples). Hoy los `make test-*` validan que los examples corren
      end-to-end; no testean los snippets pre-aprobados en
      `skills/<name>/SKILL.md` ni los edge cases que cubren (e.g.
      `pandas-cleaning` con dtype mixto, `feature-engineering` con
      target desbalanceado). Esto bloquea confianza en upgrades.
- [ ] **Review del dialecto Databricks (Spark SQL)** recién agregado en
      v0.9.0. Validar cobertura offline (snippets de
      `DATE_TRUNC`, `IFF`, `TRY_CAST`, window functions con
      `BETWEEN ... AND ...` vs `ROWS BETWEEN`) y gaps reales contra
      Postgres/Snowflake.
- [ ] **CHANGELOG.md y PRDs al día** (este doc + flip de los 7 PRDs a
      Accepted).
- [ ] **`docs/architecture.md` cross-linked** desde `AGENTS.md` y
      `README.md`.

### Out of scope para v1.0 (planeado para v1.x)

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

- **Minor (0.x.0)** cuando se agrega una skill nueva o un agente
  nuevo, o cuando cambia la forma de orquestación entre agentes.
- **Patch (0.x.y)** cuando se arregla un bug, se mejora un snippet
  pre-aprobado, o se sincroniza documentación.
- **Major (x.0.0)** reservado para cambios incompatibles en el
  frontmatter de las skills o en el contrato del instalador
  (`bin/install.js`). El primer major será v1.0.0 cuando los
  criterios de arriba estén cumplidos.

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
