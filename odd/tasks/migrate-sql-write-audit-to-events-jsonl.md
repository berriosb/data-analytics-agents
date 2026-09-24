# Feature: migrate-sql-write-audit-to-events-jsonl

**Status:** in_progress
**Branch:** main (autorizado por el usuario; sin PR por ahora)
**Goal:** cerrar la inconsistencia pre-existente entre el spec y el código de
`sql-write` respecto al path del audit log. El spec dice transversal
(`~/.agents/audit/events.jsonl` con `AUDIT_LOG_DIR`); el código escribe a
su propio archivo (`sql-write.log` con `SQL_WRITE_AUDIT_DIR`). Esta feature
alinea el código con el spec.

## Contexto

El usuario modificó el SKILL.md de `sql-write` documentando el path nuevo
(`events.jsonl` transversal con `audit-log`). Pero no tocó el código. Si
commiteamos solo el doc, queda una mentira: el usuario lee la doc, ejecuta
`execute_insert`, busca el log en `events.jsonl`, no encuentra nada,
encuentra `sql-write.log`, y se pregunta por qué la doc miente.

Tres archivos en juego:

1. `skills/sql-write/recetas/audit.py` — el código real (8 referencias al path/env viejos)
2. `docs/prd/sql-write.md` línea 112 — PRD desactualizado
3. `AGENTS.md` fila de `reporting-analyst (deploy servicio)` — typo de markdown:
   `*api-builder*` (un asterisco, italics) debería ser backticks como el resto
   de la tabla.

## Scope

- Migrar `audit.py`:
  - Path: `~/.agents/audit/sql-write.log` → `~/.agents/audit/events.jsonl`
  - Env var: `SQL_WRITE_AUDIT_DIR` → `AUDIT_LOG_DIR`
  - Rotación: `sql-write.log.{1..10}` → `events.jsonl.{1..10}`
  - Mantener firma de `audit_log()` y `get_audit_path()` (importadas por
    examples y por el SKILL.md).
  - Formato JSONL idéntico al de `audit-log/backend.py` para que un
    `jq 'select(.skill=="sql-write")' events.jsonl` funcione uniforme.
- Actualizar `docs/prd/sql-write.md` línea 112 con el nuevo path.
- Corregir `AGENTS.md`: `*api-builder*` → `api-builder` (backticks).
- Verificar: tests, install list, smoke test de la rotación.

Fuera de scope:

- No tocar `skills/audit-log/recetas/backend.py` — ese ya está correcto.
- No fusionar las dos implementaciones en una sola librería compartida
  (sería un refactor mayor; hoy cada skill tiene su `audit.py` privado).
- No agregar campos nuevos al JSONL — solo cambiar el path.

## Tasks

Ver `todo` activa.

## Acceptance criteria

- `audit.py` escribe a `~/.agents/audit/events.jsonl` por defecto,
  override por `AUDIT_LOG_DIR`.
- Rotación a 1MB → `events.jsonl.1` ... `events.jsonl.10`.
- `audit_log()` y `get_audit_path()` mantienen la firma.
- `docs/prd/sql-write.md` actualizado.
- `AGENTS.md` corregido.
- `make test-unit` verde.
- Smoke test manual: ejecutar `execute_insert()` y verificar que el log
  aparece en `events.jsonl`, no en `sql-write.log`.

## Evidence (commits)

Pendiente.

## Risks

- Bajo: los tests no dependen del path (verificado).
- Bajo: el formato JSONL es idéntico al anterior (mismo dict, misma
  serialización `json.dumps`).
- Medio: si un usuario ya tenía `~/.agents/audit/sql-write.log` con
  entradas, la migración no las migra — empieza de cero en
  `events.jsonl`. Documentar en CHANGELOG como nota.
