# PRD — `audit-log`

- **Status:** Draft → Ready para implementar tras ADR-002 aceptado
- **Owner:** CodeHak (Bastian)
- **ADR relacionado:** [002-end-to-end-delivery](../adr/002-end-to-end-delivery.md)
- **Skills relacionadas:** `sql-cloud-warehouse`, `sql-write`, `sql-analyst`, `audit-log` (transversal: lo carga cualquier skill que toque una DB)

## Goal

Que un manager pueda responder "¿quién corrió qué query contra el
warehouse y cuándo?" leyendo un log estructurado, append-only, con
redaction automática de PII y rotación por tamaño.

## User story

> Como data analyst en una fintech, en 3 meses me van a preguntar
> "¿qué queries corrió el equipo contra el warehouse la semana
> pasada?" o "¿alguien leyó datos de clientes sin autorización?".
> Necesito que el toolkit registre automaticamente cada SELECT/INSERT
> que se ejecutó: quién (qué agente/usuario), cuándo (timestamp),
> qué (query + preview), desde dónde (engine + DB), cuánto tardó,
> cuántas filas se afectaron. Sin que el data analyst tenga que
> acordarse de hacer logging manual.

## Scope in (v1)

- **Log JSONL append-only**: una linea JSON por evento.
  Campos: `timestamp`, `actor` (agente o user), `action`
  (`select`, `insert`, `create`, `dry-run`, `rejected`),
  `engine`, `target`, `status` (`ok`|`failed`|`rejected`),
  `n_rows`, `duration_ms`, `sql_preview`, `error`, `redacted_fields`.
- **Multi-backend**:
  - **JSONL** (default): `~/.agents/audit/events.jsonl` con rotacion
    por tamano (1MB → `events.jsonl.1`, etc., max 10 archivos).
  - **SQLite** (opcional): `~/.agents/audit/events.sqlite` para
    queries (`SELECT * WHERE action = 'select' AND ...`). El usuario
    elige via env var `AUDIT_LOG_BACKEND=jsonl|sqlite`.
- **Redaction automatica de PII** via regex configurables:
  - Default: email, RUT chileno (`12.345.678-9`), telefono CL
    (`+56 9 XXXX XXXX`), tarjeta de credito (16 digitos).
  - Custom: el usuario puede pasar patrones adicionales via env var
    `AUDIT_LOG_REDACT_REGEX` (separados por `|`).
  - En el JSONL se guarda `redacted_fields: ['email', 'rut']` y los
    valores reemplazados por `***REDACTED***`.
- **API de lectura** (queries sobre el log):
  - `query_audit(actor=None, action=None, since=None, until=None,
    limit=100) -> list[dict]`
  - Filtros combinables. Si backend=sqlite, usa SQL; si backend=jsonl,
    carga los archivos y filtra en memoria (suficiente para archivos
    historicos pequenos).
- **NO contenido completo del query** en v1: solo `sql_preview`
  (primeros 200 chars). El usuario puede setear `AUDIT_LOG_FULL_SQL=true`
  para guardar el query completo (warning: queries largos pueden
  revelar PII).

## Scope out (v1, queda como follow-up)

- **Forwarding a servicio externo** (Datadog, OpenTelemetry, Loki):
  ADR-003. La skill escribe a disco; integraciones externas quedan
  como sinks opcionales.
- **Tamper-evident log** (blockchain-style hash chaining): ADR-003.
  En v1 confiamos en append-only del filesystem (permisos del OS).
- **UI / dashboard para explorar el log**: ADR-003. En v1 solo CLI/Python.
- **Streaming writes** (multi-proceso): en v1 cada proceso escribe su
  propia linea (con `O_APPEND` atomic en POSIX). Multi-proceso real
  con archivo lock queda como follow-up.

## Workflow (las 6 fases de la skill)

1. **Inicializar el backend**: `init_audit_log()` crea el archivo/dir
   con permisos `0600` (solo el usuario puede leer/escribir). Si el
   backend es SQLite, crea la tabla `events`.
2. **Escribir eventos**: `audit_log(event_dict)` agrega al JSONL o
   SQLite. Aplica redaction ANTES de escribir. Si el archivo activo
   supera 1MB, rota.
3. **Redaction**: helper `_redact_pii(text) -> (text, list)` que aplica
   los regex configurados y devuelve el texto redactado + la lista de
   campos redacted. Por defecto: email, RUT, telefono CL, tarjeta.
4. **Query**: `query_audit(...)` lee segun filtros y devuelve lista de
   eventos. En backend=sqlite, usa SQL con `WHERE` dinamico. En
   backend=jsonl, lee archivos historicos (max 10) + archivo activo.
5. **Rotacion**: cuando el archivo activo supera 1MB, renombra a
   `events.jsonl.1` (el `.10` mas viejo se borra). El backend SQLite
   no requiere rotacion porque ya esta indexado.
6. **Tamper-evident opcional** (no en v1): si el usuario quiere
   garantia criptografica, generar hash chain. v1 es best-effort.

## Recetas iniciales (snippets pre-aprobados)

- `init_audit_log(backend=None) -> Path` — crea dir/archivo/tabla
- `audit_log(event_dict)` — escribe un evento (con redaction)
- `query_audit(actor=None, action=None, since=None, until=None,
  limit=100) -> list[dict]` — query sobre el log
- `set_redact_patterns(extra_patterns)` — agregar regex custom
- `rotate_if_needed() -> None` — para uso manual o cron

## Verificación (criterios de "listo")

- [ ] `examples/audit_log_sample/` con:
  - Script que genera 10 eventos de muestra con PII (email, RUT, telefono)
  - Verificacion de que el JSONL no contiene los valores reales
    (solo `***REDACTED***` y la lista de campos)
  - Query de ejemplo filtrando por `actor` y `action`
- [ ] `make test-audit-log` ejecuta el demo y verifica:
  - 10 eventos escritos
  - 0 valores de PII en el JSONL (assertion: ningun email real)
  - Query por filtro devuelve los eventos correctos
- [ ] La skill esta en `skills/audit-log/SKILL.md` con el template
      de 6 secciones completo.
- [ ] `AGENTS.md` actualizado: cualquier agente que toque DB
      (`sql-analyst`, `sql-cloud-warehouse`, `sql-write`) carga
      `audit-log` automaticamente (transversal).
- [ ] `bin/install.js` corre sin cambios.

## Estimación

- Specs + sample: 30 min (hecho).
- Implementacion SKILL.md + recetas: 1.5-2 horas.
- Demo + tests con redaction: 30-45 min.
- Wiring (AGENTS.md, Makefile, package.json): 15 min.

**Total: ~3 horas de código + tests.**