# ADR-002 — Extender el toolkit para entrega end-to-end (analisis → servicio)

> Propósito: Capturar las decisiones arquitectónicas para agregar `api-builder`,
> `excel-formulas`, `sql-write` y `audit-log` al toolkit, derivadas del gap
> que existe entre "terminé el análisis" y "lo entregué al cliente/jefe".

- **Status:** Aceptado (2026-09-14)
- **ADR previo:** [001-portable-day1](./001-portable-day1.md) (cerrado en v0.4.0)

## Contexto

El toolkit v0.4.0 cierra el ciclo del analista (datos sucios → reporte ejecutivo).
Pero en una pega real, después del reporte suele venir **entregar el análisis
como servicio**: el director quiere ver el dashboard actualizado cada lunes, el
cliente quiere consultar el endpoint REST, o el equipo de producto quiere
embebir el forecast en su app.

Ese paso — convertir análisis estático en servicio vivo — es el que falta.
Hay 4 brechas concretas:

1. **API builder** — el toolkit produce notebooks y reportes, no servicios. Un
   data analyst en una fintech o retail chileno llega el lunes y le piden
   "expón el forecast como endpoint para el equipo de pricing". Sin api-builder,
   tiene que escribir FastAPI a mano desde cero (y romper la consistencia con
   el resto del toolkit).
2. **Excel formulas** — `excel-profiler` lee valores pero no fórmulas. Para
   auditoría financiera (¿cómo se calculó este margen?), el data analyst
   necesita ver la fórmula, no solo el número.
3. **SQL write guarded** — `sql-analyst` y `sql-cloud-warehouse` son
   **solo lectura** (SELECT únicamente). Cuando el data analyst necesita
   persistir resultados (crear tabla con top-100 clientes), no hay flujo
   seguro. Sin guardrails, es copy-paste destructivo.
4. **Audit log** — en producción, el manager pregunta "¿quién corrió qué
   query contra el warehouse y cuándo?". Sin log, el data analyst improvisa.

Estas 4 skills existen para que el sistema **llegue y produzca servicio el
día 1**, no para展示.

## Decisiones arquitectónicas

### 1. Stack de cada skill nueva

| Skill | Librería base | Por qué |
|---|---|---|
| `api-builder` | FastAPI + uvicorn + pydantic | FastAPI es el estándar moderno para APIs Python. uvicorn para servir. pydantic para validar inputs/outputs. Sin reinventar. |
| `excel-formulas` | `formulas` (librería de Excel) + openpyxl | `formulas` parsea fórmulas Excel a AST Python. openpyxl lee valores (ya usado en excel-profiler). |
| `sql-write` | SQLAlchemy Core (existente) + `sqlalchemy.sql.ddl` | SQLAlchemy ya está. DDL es dialecto-aware. NO usar `eval()` ni SQL crudo del usuario sin guards. |
| `audit-log` | JSON append-only + sqlite opcional | Sin servicio externo. JSON por defecto (compatible con cualquier pipeline). SQLite opcional para queries sobre el log. |

### 2. Formato de skill — mismo template que las 16 existentes

Las 4 siguen el template de 6 secciones:
- Descripción general
- Cuándo usar (con trigger phrases)
- Flujo de trabajo (paso a paso)
- Justificaciones comunes
- Señales de alerta
- Verificación

Sin frontmatter especial. Sin configuración nueva en `bin/install.js`.

### 3. Personas que referencian estas skills

- `api-builder`: lo carga **un nuevo agente `deployer`** o `reporting-analyst`
  como paso opcional al final del flujo (después de `report-export`).
- `excel-formulas`: lo carga `data-explorer` cuando el usuario pide auditar
  fórmulas (no por defecto — solo si el usuario lo pide explícitamente).
- `sql-write`: lo carga `sql-analyst` SOLO si el usuario pide escribir/crear
  tabla (con guardrails explícitos: dry-run obligatorio, confirmación doble).
- `audit-log`: lo carga cualquier agente que toque DB. Es transversal.

### 4. Multi-CLI compatibility — sin cambios

Las 4 skills son markdown + snippets Python. Se distribuyen via el patrón
existente (`npx data-analytics-agents install --all`). No requiere tocar
`bin/install.js`.

### 5. Guardrails — la prioridad es la seguridad

- **`sql-write`:** dry-run obligatorio antes de ejecutar. Confirmación
  explícita del usuario (tipo "sí, ejecuta el DROP TABLE"). Log de la query
  al audit-log ANTES de correrla. Rollback script generado si la query es
  DROP/RENAME.
- **`api-builder`:** los endpoints generados validan inputs con pydantic
  (no aceptar SQL injection via path params). Auth opcional (API key via
  env var, no JWT/OAuth en v1).
- **`audit-log`:** append-only. NO permite borrar entries. Rotación a
  archivo nuevo cuando el archivo activo supera 10MB.

### 6. Distribución — sigue siendo una sola publicación npm

Las 4 skills viven en `skills/<name>/SKILL.md` y se incluyen en el paquete
existente. No hay paquetes separados.

## Trade-offs considerados

### ¿Por qué `api-builder` con FastAPI y no Flask?

Flask es más simple pero FastAPI genera docs automáticas (OpenAPI/Swagger),
valida inputs con pydantic, y es async-native. Para entregarle al manager
"ya hay docs en `/docs`", FastAPI gana.

### ¿Por qué no usar `streamlit` para "deployar análisis"?

Streamlit es para prototipos internos, no para entregar a cliente. FastAPI
es el estándar de API REST. Si más adelante hay demanda de UI, va como
`stakeholder-ui` aparte.

### ¿Por qué no incluir Databricks SQL en este pase?

Databricks tiene su propio dialecto (Spark SQL) que difiere de Snowflake/BQ.
Agregar soporte real toma 2-3 días (snippets, validación, errores). Lo dejo
para ADR-003 si hay demanda.

### ¿Por qué audit-log como JSON y no servicio externo?

Servicio externo (Datadog, OpenTelemetry) agrega dependencia operacional
y credenciales. JSON append-only es debuggeable con `cat` y `jq`. Si más
adelante hay demanda, se le agrega un sink opcional.

## Riesgos

- **`formulas` tiene limitaciones con fórmulas complejas** (INDIRECT, OFFSET,
  algunas lambda). Documentado: si falla, fallback a openpyxl leyendo
  `cell.value` (valor) y mostrar warning "no se pudo parsear la fórmula".
- **`sql-write` con DDL es destructivo.** Solución: dry-run obligatorio,
  doble confirmación, audit log antes/después. Sin bypass.
- **`api-builder` generar código que el usuario no entiende.** Solución: el
  output de la skill es **código generado + instrucciones para correrlo**, no
  un servicio ya corriendo. El usuario decide cuándo y dónde servirlo.
- **`audit-log` sensible a PII.** Solución: permite redactar columnas via
  config (`audit.redact = ['email', 'phone']`). Default redacta todo lo que
  matchee patrones PII comunes (regex emails, RUT chileno, etc.).

## Relación con ADRs/PRD existentes

- `AGENTS.md` — referencia a las 4 skills nuevas (actualizar tras implementación).
- `README.md` — mención en la tabla de skills y en "Convenciones".
- `bin/install.js` — **sin cambios**. La instalación multi-CLI ya soporta
  skills arbitrarios.
- `examples/` — agregar:
  - `examples/api_builder_sample/` — FastAPI app generada + demo
  - `examples/excel_formulas_sample/` — Excel con fórmulas de muestra
  - `examples/sql_write_sample/` — demo de CREATE TABLE con dry-run
  - `examples/audit_log_sample/` — log de muestra + queries sobre él

## PRDs asociados

- `docs/prd/api-builder.md`
- `docs/prd/excel-formulas.md`
- `docs/prd/sql-write.md`
- `docs/prd/audit-log.md`

## Estimación

- Specs + ADR: 1h (hecho)
- `api-builder` (skill + recetas + demo + tests): ~5-6h
- `excel-formulas` (skill + recetas + demo + tests): ~3-4h
- `sql-write` (skill + recetas + demo + tests con guardrails): ~5-6h
- `audit-log` (skill + recetas + demo + tests): ~2-3h
- AGENTS.md + package.json + release: 1h

**Total: ~17-21h de código + tests.** Distribuir en 2-3 sesiones.