# Changelog

Todos los cambios visibles para el usuario en este toolkit. El formato está
inspirado en [Keep a Changelog](https://keepachangelog.com/) y el versionado
sigue [SemVer](https://semver.org/). La fuente de verdad para el alcance de
cada release es `package.json` + los PRDs en [`docs/prd/`](docs/).

## [1.2.1] — 2026-09-24

### Fixed

- **`pyproject.toml` missing from npm tarball** — Added to
  `package.json#files[]`. v1.2.0 documented the new `pyproject.toml`
  under [Added] but the file was not actually included in the npm
  tarball because `files[]` did not list it. Symptom: users running
  `npm install --save-dev data-analytics-agents` followed by
  `pip install -e .[dev]` would fail with "pyproject.toml not found".
  Fix: list `pyproject.toml` in `files[]` and bump to 1.2.1. No code
  or behavior change — the v1.2.0 commit (`27496e7`) was never
  published to npm registry, so this is the first npm release with
  the new packaging.

## [1.2.0] — 2026-09-24

Cierra la inconsistencia pre-existente entre el spec transversal del
audit log y el código de `sql-write`, y explicita el canal Python local
que antes vivía disperso entre `requirements-dev.txt` y las peerDeps
mentirosas de `package.json`.

### Added

- **`pyproject.toml`** — Metadata + `[project.optional-dependencies]`
  para el canal Python local (extras: `dev`, `excel`, `sql`, `cloud`,
  `viz`, `api`, `all`). Backend `hatchling` con `only-include =
  ["pyproject.toml"]` para wheel metadata-only. **NO se publica a
  PyPI** (classifier `Private :: Do Not Upload`). Reemplaza las
  peerDeps Python que vivían en `package.json` (npm las ignoraba
  silenciosamente, confundía a contribuidores que esperaban que
  `npm install` instale pandas). Flujo recomendado: `pip install -e
  .[dev]` para tests y recipes; `pip install -e .[cloud]` para
  drivers Snowflake/BQ/Redshift/Databricks; `pip install -e .[all]`
  para todo.
- **README — "Trabajar con las recetas localmente (Python)"** —
  Nueva sección que documenta el flujo `pip install -e .[dev]` + el
  `skills_loader.py` bootstrap para usar las recetas desde scripts
  y tests.

### Changed

- **`skills/sql-write/recetas/audit.py`** — Migración del audit log
  al archivo transversal `~/.agents/audit/events.jsonl` (env var
  `AUDIT_LOG_DIR`), alineado con la skill `audit-log` (transversal).
  Antes escribía a `~/.agents/audit/sql-write.log` con env var
  `SQL_WRITE_AUDIT_DIR`. Rotación `events.jsonl.1..10` (antes
  `sql-write.log.1..10`). Esquema JSONL ampliado con `actor=None`
  (filtrado cuando None, pero presente en la spec para uniformidad
  con `audit-log/backend.py` — un `jq 'select(.engine=="sqlite")'`
  ahora ve entries de `sql-write` y `audit-log` en el mismo archivo).
  **Breaking para downstreams**: herramientas que leían `sql-write.log`
  deben migrar a `events.jsonl`. Las entries nuevas conviven con las
  de `audit-log`, distinguibles por `action`/`engine`.
- **`skills_loader.py`** — API pública completa: nuevo `bootstrap()`
  como entry point único que reune `load_skill_packages()` +
  `prime_and_alias_submodules()` (antes la lógica vivía duplicada
  entre este archivo y `tests/conftest.py`). Auto-descubrimiento
  de pares hyphen↔underscore (el `SKILL_NAME_PAIRS` hardcoded de
  `conftest.py` se eliminó). Docstring completo explicando por qué
  existe (Python no acepta guiones en nombres de módulos; los
  nombres siguen la convención de skills.sh).
- **`tests/conftest.py`** — Reducido a 31 líneas; llama
  `skills_loader.bootstrap()` directo. Elimina duplicación de
  `_bootstrap_skills_loader` y `_prime_and_alias_skill_submodules`.
- **`package.json`** — `peerDependencies` y `peerDependenciesMeta`
  vaciados (eran ruido que npm ignoraba). Description actualizada
  para apuntar a `pyproject.toml`.
- **`requirements-dev.txt`** — Reorganizado por dominio de skill.
  Sigue funcionando como shortcut para `pip install -r
  requirements-dev.txt`, pero la fuente canónica es ahora
  `pyproject.toml [project.optional-dependencies.dev]`.
- **`AGENTS.md`** — Reorganización de la tabla de agentes:
  consolidada la fila `(transversal)` de `audit-log` en cada agente
  que la carga, marcado `(opcional)` en skills que ya eran opt-in
  (`statistical-testing`, `time-series-patterns`, `insight-synthesis`),
  eliminadas filas redundantes de sub-casos (`data-explorer (Excel
  corporativo sucio)`, `reporting-analyst (export ejecutivo)`).
  Agregado `excel-profiler` al inicio del flujo de `data-explorer`
  (coherente con ADR-001).

### Fixed

- **`AGENTS.md`** — Typo markdown `*api-builder*` →
  `` `api-builder` `` en la fila `reporting-analyst (deploy
  servicio)`. Un solo asterisco se renderiza como italics; los
  backticks son consistentes con el resto de la tabla.

### Repository tooling

- **`.gitignore`** — Agregado `.atl/` (estado local de Pi runtime;
  antes untracked y en riesgo de commit accidental).

## [1.1.0] — 2026-09-15

Release menor post-v1.0.1. Agrega OAuth2 / service-principal opcional
para Snowflake y Databricks (sin romper los flows existentes),
`make doctor` preflight, `CONTRIBUTING.md`, QUALIFY snippet, y unit
tests para csv-profiler / viz-patterns / statistical-testing.

### Added

- **OAuth2 / service-principal para `sql-cloud-warehouse`** (ADR-003):
  - Snowflake OAuth: nuevo auth_method `oauth` via `SNOWFLAKE_OAUTH_TOKEN`
    (access token externo emitido por IdP corporativo).
  - Databricks service principal: nuevo auth_method `service_principal`
    via `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET` +
    `DATABRICKS_OIDC_ENDPOINT` (client credentials flow via
    `databricks-sdk`, peerDep opcional nuevo).
  - `detect_auth_method()` auto-detecta: si los vars de OAuth/SP
    estan seteados usa esos; si no, cae a password/PAT (backward
    compatible).
  - `databricks-sdk` agregado como peerDep opcional.
- **`scripts/doctor.py` (`make doctor`)** — preflight de versiones
  y peer-deps. Chequea Node >= 18, Python >= 3.10, git, deps core
  REQUIRED (pandas, numpy, openpyxl, plotly, sqlalchemy), deps
  OPTIONAL por skill, estructura del repo (AGENTS.md, agents/,
  skills/, 20 SKILL.md), y smoke test del installer. Output con
  ANSI colors + hints accionables (`pip install ...`).
- **`CONTRIBUTING.md`** — guia paso a paso para agregar snippets,
  skills y agentes. Tipos de contribucion (bug / snippet / skill /
  agente), estructura del repo, setup local, convenciones, tests,
  PR review checklist. Cross-linked desde `README.md`.
- **QUALIFY clause snippet** en `sql-cloud-warehouse.dialect_snippets`
  — emite `QUALIFY <cond>` para Databricks (Spark SQL 3.2+) y
  Snowflake (2023+); levanta `UnsupportedQualifyError` con receta
  de reescritura para BigQuery y Redshift. Cierra el gap G2 del
  review de Databricks.
- **Unit tests para 3 skills sin `recetas/`**:
  - `csv-profiler` — `recetas/normalize.py` (NULL_TOKENS,
    normalize_nulls, null_count) + `recetas/profile.py`
    (count_outliers_iqr, numeric_stats, categorical_top,
    datetime_range, profile_column). 30 tests.
  - `viz-patterns` — `recetas/chart_selector.py`
    (recommend_chart_type, validate_pie,
    validate_bar_x_not_categorical_for_line, orientation_for_labels).
    19 tests.
  - `statistical-testing` — `recetas/effect_size.py` (cohen_label,
    eta_squared_label, cohens_d) + `recetas/tests.py` (t_test_ind,
    mann_whitney_u, anova_oneway). 30 tests.
- **`docs/notes/databricks-coverage.md`** (de v1.0.0) — review del
  dialecto Databricks con cobertura + gaps priorizados.

### Changed

- **`scripts/doctor.py`** — `make doctor` agregado al `Makefile` y al
  README sección Tests. Sin cambios a `make test`.
- **`tests/conftest.py`** — `SKILL_NAME_PAIRS` ahora cubre 9 skills
  (los 6 originales + csv-profiler / viz-patterns /
  statistical-testing). Aliasing de submodulos hyphen<->underscore
  funciona para los nuevos.

### Documentation

- **`docs/adr/003-oauth2-cloud-warehouses.md`** — ADR nuevo
  documentando las decisiones de OAuth (scope por warehouse, stack,
  dispatch, guardrails, trade-offs).
- **`CONTRIBUTING.md`** — guia paso a paso para contribuidores
  (cross-linked desde README).

## [1.0.1] — 2026-09-15

## [1.0.1] — 2026-09-15

Patch release: sincronización de documentación + guardrail pre-publish.

### Fixed

- **`AGENTS.md` y `README.md`** — corregido el conteo de "4 personas" → "5
  personas" en 3 lugares (sección "Inicio rápido", sección "Por qué este
  archivo solo no alcanza", tabla de CLI en README). El toolkit siempre
  tuvo 5 personas; el doc arrastraba un número incorrecto desde antes
  de que se agregara `using-data-analytics-agents`.

### Changed

- **`package.json#description`** — la descripción ahora es concisa y
  descubrible (qué hace el paquete, cuántos agentes/skills incluye).
  El contexto de release notes se movió al CHANGELOG (que es donde
  corresponde).
- **`package.json#scripts`** — agregado `prepublishOnly`:
  `node ./bin/install.js list && make test-unit`. Bloquea `npm publish`
  si los symlinks no están bien o los 161 unit tests fallan. Agregado
  también `test` y `test:unit` como atajos.

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

Items **no incluidos en v1.0.1** que se podrán agregar en futuras versiones
de la serie 1.x:

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
