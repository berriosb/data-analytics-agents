---
name: audit-log
description: Audit log transversal del toolkit: registra cada operacion que toca una DB (SELECT/INSERT/CREATE/UPDATE/DELETE) en un JSONL append-only o SQLite, con redaction automatica de PII (email, RUT CL, telefono CL, tarjeta). Usado por sql-analyst, sql-cloud-warehouse y sql-write para responder 'quien corrio que query y cuando'. Default en ~/.agents/audit/events.jsonl con permisos 0600 y rotacion automatica a 1MB. Backend alternativo via env var AUDIT_LOG_BACKEND=sqlite.
---

# Audit Log

Log transversal del toolkit para responder "¿quién corrió qué query
contra la warehouse y cuándo?" con redaction automática de PII.

## Descripción general

A diferencia del resto de las skills (que viven en el flujo de trabajo),
esta es **transversal**: la cargan `sql-analyst`, `sql-cloud-warehouse` y
`sql-write` para registrar cada operación que tocan una DB. NO es una
skill que el agente invoca explícitamente — se invoca automáticamente
como side effect de las otras.

El log es **append-only JSONL** con permisos `0600` (solo el usuario
puede leer/escribir) y rotación automática cuando supera 1MB (mantiene
hasta 10 archivos históricos).

## Cuando se invoca (transversal)

Esta skill NO se invoca explícitamente — las otras la llaman como side
effect:

- `sql-analyst` → registra cada `SELECT` ejecutado
- `sql-cloud-warehouse` → registra cada query contra Snowflake/BQ/Redshift
- `sql-write` → registra cada `INSERT`/`CREATE` exitoso o fallido,
  y cada `DROP`/`UPDATE`/`DELETE` rechazado por el validator

**Si** necesitás leer el log directamente, usá `query_audit(...)`:

```python
from audit_log.recetas import query_audit

# Todos los eventos del agente 'sql-analyst' en las ultimas 24h
eventos = query_audit(actor="sql-analyst", since="2026-09-13T00:00:00")
```

## Backends

**JSONL (default):** `~/.agents/audit/events.jsonl`
- Append-only, una línea JSON por evento
- Permisos `0600`
- Rotación automática a 1MB → `events.jsonl.1`, `.2`, ..., `.10`
- Queries: en memoria (lee archivos de rotación + activo)

**SQLite (opcional):** `~/.agents/audit/events.sqlite`
- Activado con `AUDIT_LOG_BACKEND=sqlite`
- Tabla `events` con índices en `actor`, `action`, `timestamp`
- Queries: SQL nativo (más rápido para >10K eventos)

```bash
# Switch a SQLite (los eventos futuros van alla; los JSONL anteriores
# NO se migran automaticamente en v1)
export AUDIT_LOG_BACKEND=sqlite
```

## Redaction de PII

Cada valor de `sql_preview` y `error` pasa por `redact_pii()` antes de
guardarse. Patrones default:

| Patrón | Regex | Ejemplo |
|---|---|---|
| `email` | `\b[\w.+-]+@[\w-]+\.[\w]+\b` | `juan@banco.cl` |
| `rut_cl` | `\d{1,2}\.?\d{3}\.?\d{3}[-][\dkK]` | `12.345.678-9` |
| `phone_cl` | `(?:\+?56\s?)?(?:9\s?)?[2-9]\d{3}\s?\d{4}` | `+56 9 8765 4321` |
| `credit_card` | `\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}` | `1234 5678 9012 3456` |

Los matches se reemplazan por `***REDACTED:<nombre>***` y el campo
`redacted_fields` del evento guarda la lista de nombres detectados.

**Custom patterns** via env var (separados por `|`):
```bash
export AUDIT_LOG_REDACT_REGEX="cuit_ar:\d{11}|ip:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}"
```

## Esquema de un evento

```json
{
  "timestamp": "2026-09-14T19:16:17+00:00",
  "actor": "data-explorer",
  "action": "select",
  "engine": "snowflake",
  "target": "analytics.transactions",
  "status": "ok",
  "n_rows": 1000,
  "duration_ms": 230,
  "sql_preview": "SELECT * FROM transactions WHERE cliente_rut = '***REDACTED:rut_cl***'",
  "redacted_fields": ["rut_cl"]
}
```

`status` puede ser `ok`, `failed` o `rejected`.

## Recetas pre-aprobadas (importables)

```python
import sys
sys.path.insert(0, "ruta/al/repo")
from skills_loader import load_skill_packages
load_skill_packages("skills")

from audit_log.recetas import (
    init_audit_log,
    audit_log, audit_event, AuditEvent,
    query_audit,
    redact_pii, set_extra_patterns,
    JsonlBackend, SqliteBackend,
    AUDIT_DIR, LOG_FILE,
)
```

## CLI rápido

```bash
# 1. Generar eventos de muestra con PII
python examples/audit_log_sample/generate_sample.py

# 2. Demo end-to-end (verifica NO PII en el log + queries)
python examples/audit_log_sample/demo_offline.py

# 3. Ad-hoc: escribir un evento custom
python -c "
import sys, os; sys.path.insert(0, '.')
from skills_loader import load_skill_packages
load_skill_packages('skills')
from audit_log.recetas import init_audit_log, audit_log, audit_event
init_audit_log()
audit_log(audit_event(
    actor='mi-agente', action='select', engine='sqlite',
    target='mi_tabla', status='ok', n_rows=42,
    sql_preview='SELECT * FROM mi_tabla WHERE email = \"foo@bar.com\"',
))
print('OK')
"

# 4. Ad-hoc: query
python -c "
import sys; sys.path.insert(0, '.')
from skills_loader import load_skill_packages
load_skill_packages('skills')
from audit_log.recetas import query_audit
for e in query_audit(limit=10):
    print(e['timestamp'], e['action'], e['target'])
"
```

## Justificaciones comunes

- **Por qué JSONL default y no SQLite?** JSONL es append-only real,
  sin riesgo de corrupcion si el proceso muere a mitad de un INSERT,
  y se inspecciona con `cat | jq` sin tooling extra. SQLite es la
  opcion para volumen alto (>10K eventos) o queries frecuentes.
- **Por qué redaction automatica y no opt-in?** Porque el costo de
  un PII leak es alto (compliance, GDPR, etc.) y el costo de redactar
  es bajo. Si querés guardar el SQL completo, seteás
  `AUDIT_LOG_FULL_SQL=true` pero no es default.
- **Por qué `0600` y no `0644`?** Porque el log contiene queries con
  potencial PII. Solo el usuario que lo generó debe poder leerlo.
- **Por qué rotation automatica?** Para evitar que el archivo crezca
  indefinidamente. 1MB es chico (~10K eventos), fácil de inspeccionar.

## Señales de alerta

- **Permisos del log no son `0600`**: alguien o algo los cambió. La
  skill NO los corrige automáticamente (mejor que el usuario sepa).
- **`redacted_fields` está poblado pero `sql_preview` parece "limpio"**:
  el patrón matcheó algo que no esperabas. Revisar la regex.
- **`status=failed` masivo del mismo actor**: puede ser bug del agente
  o credenciales expiradas.
- **`action=rejected` masivo**: alguien está intentando DROP/UPDATE.
  Vale la pena revisar quién.
- **El log activo pesa cerca de 1MB**: la rotación va a ocurrir
  pronto. Si se rota muy seguido (>1 vez/día), considerar SQLite.

## Verificación

Criterios de "listo" (ver `docs/prd/audit-log.md`):

- [x] `examples/audit_log_sample/` con generador de 10 eventos + demo.
- [x] `make test-audit-log` ejecuta el demo y verifica:
  - 10 eventos escritos
  - 0 valores de PII en el JSONL (5 patrones verificados)
  - Permisos `0600`
  - Queries con filtros funcionan
- [x] La skill está en `skills/audit-log/SKILL.md` con el template
      de 6 secciones completo.
- [x] `AGENTS.md` actualizado: `sql-analyst`, `sql-cloud-warehouse`,
      `sql-write` cargan `audit-log` transversalmente.
- [x] `bin/install.js` corre sin cambios.

## Dependencias

- **stdlib only** (json, sqlite3, re, pathlib, os).
- Sin pandas, sin sqlalchemy, sin requests. La skill es 100% stdlib.

Esta es la skill más liviana del toolkit — no requiere deps externas
para funcionar.