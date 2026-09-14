---
name: sql-write
description: Persiste resultados de analisis en una DB de manera segura (modo conservador). Usar SOLO si el usuario pide escribir/crear tablas — sql-analyst carga esta skill explicitamente con guardrails. Permite CREATE TABLE IF NOT EXISTS, INSERT (con VALUES o SELECT), CREATE INDEX/VIEW. BLOQUEA DROP/UPDATE/DELETE/TRUNCATE/ALTER/GRANT/REVOKE. Dry-run obligatorio, doble confirmacion, audit log append-only JSONL en `~/.agents/audit/sql-write.log`. Soporta SQLite local + Snowflake/BigQuery/Redshift (via sql-cloud-warehouse).
---

# SQL Write (modo conservador)

Persiste resultados de análisis en una DB **sin riesgo destructivo**. Diseñada
para el caso de uso más común de un data analyst: "terminé el análisis, quiero
que el equipo consulte este resultado mañana vía SQL".

## Descripción general

A diferencia de `sql-analyst` y `sql-cloud-warehouse` (que son **solo
lectura**), esta skill **escribe a la DB**, pero con guardrails estrictos:

- Solo permite operaciones **no destructivas** (CREATE TABLE IF NOT
  EXISTS, INSERT, CREATE INDEX/VIEW).
- **Bloquea** toda operación destructiva: DROP, UPDATE, DELETE, TRUNCATE,
  ALTER, GRANT, REVOKE.
- **Dry-run obligatorio** antes de ejecutar: muestra preview de las
  primeras 5 filas y el DDL que se va a crear.
- **Doble confirmación**: el caller (skill/agent) debe pedir
  confirmación al usuario antes de `execute_insert` (que solo acepta
  `auto_confirm=True`).
- **Audit log append-only** de cada escritura: timestamp, action,
  engine, target, n_rows, duration_ms, sql_preview.

## Cuando usar

Invocar esta skill cuando el pedido matchee con alguno de:

- "Persistí este DataFrame en una tabla para que el equipo lo consulte."
- "Creame una tabla con el top-100 clientes por revenue."
- "Insertá el resultado del modelo en `analytics.predictions_q2`."
- "Hacé un CREATE TABLE IF NOT EXISTS con estos resultados."

**No** invocar cuando:

- El usuario solo quiere **consultar** la DB → `sql-analyst` o
  `sql-cloud-warehouse` (solo lectura).
- El usuario quiere **borrar/modificar** data existente → modo full
  (ADR-003), no en v1.
- El usuario quiere escribir a un Excel/CSV plano → `data-explorer` +
  `pandas-cleaning`.

## Modo conservador (v1)

**Operaciones permitidas:**

- `CREATE TABLE [IF NOT EXISTS] <name> (...)` — crear tabla nueva (no
  falla si existe)
- `INSERT INTO <table> [(cols)] VALUES (...)` — insertar filas
- `INSERT INTO <table> SELECT ...` — insertar desde query
- `CREATE INDEX [IF NOT EXISTS] <name> ON <table> (...)` — crear indice
- `CREATE [OR REPLACE] VIEW <name> AS ...` — crear vista
- `CREATE TEMPORARY TABLE / CREATE UNIQUE INDEX` — variantes validas
- `WITH cte AS (...) INSERT INTO ...` — CTE + INSERT

**Operaciones BLOQUEADAS (mode conservador):**

- `DROP TABLE`, `DROP DATABASE`, `DROP SCHEMA`, `DROP INDEX`, `DROP VIEW`
- `UPDATE`, `DELETE`, `TRUNCATE`
- `ALTER TABLE DROP COLUMN`, `ALTER TABLE RENAME`
- `GRANT`, `REVOKE`
- Cualquier query que NO sea CREATE/INSERT

**Operaciones que requieren modo full (ADR-003, fuera de scope v1):**

- DROP TABLE, UPDATE, DELETE, TRUNCATE — necesitan rollback script
- Migraciones de schema (ALTER TABLE ADD COLUMN, RENAME)
- Bulk upsert (INSERT ... ON CONFLICT)

## Flujo de trabajo

1. **Validar target**: recibir `--target` (SQLite path o dict con
   `engine`+credenciales), `--table-name`, `--if-exists` (default
   `create-if-not-exists-else-insert`).
2. **Cargar el DataFrame** desde CSV/Parquet/Excel (pandas).
3. **Validar el SQL** propuesto (`validate_sql`) — rechaza DROP/UPDATE/etc.
4. **Dry-run** (`dry_run`): genera DDL + preview de 5 filas + chequea si
   la tabla existe. Pedir confirmación #1 al usuario.
5. **Execute** (`execute_insert` con `auto_confirm=True`): transacción
   SQLAlchemy, rollback si falla. Pedir confirmación #2 al usuario.
6. **Audit log** + reporte: query ejecutada, n_rows, duration_ms, status.

## Recetas pre-aprobadas (importables)

```python
import sys
sys.path.insert(0, "ruta/al/repo")
from skills_loader import load_skill_packages
load_skill_packages("skills")

from sql_write.recetas import (
    validate_sql,                  # (bool, msg) o BlockedOperationError
    connect_target,                # SQLite path o dict cloud
    dry_run,                       # -> dict (ddl, preview_rows, n_rows, ...)
    execute_insert,                # -> dict (n_rows, duration_ms, ...)
    audit_log,                     # escribir al JSONL log
    get_audit_path,                # ~/.agents/audit/sql-write.log
    SqlWriteError, BlockedOperationError,
)
```

`execute_insert` **requiere** `auto_confirm=True`. Si no, levanta
`SqlWriteError` con el mensaje "el caller debe pedir confirmacion al
usuario antes de llamar con auto_confirm=True".

## CLI rápido (uso desde el agente o terminal)

```bash
# 1. Generar sample
python examples/sql_write_sample/generate_sample.py

# 2. Demo end-to-end (incluye test del bloqueo de DROP)
python examples/sql_write_sample/demo_offline.py

# 3. Ad-hoc contra tu propio CSV
python -c "
import sys, pandas as pd; sys.path.insert(0, '.')
from skills_loader import load_skill_packages
load_skill_packages('skills')
from sql_write.recetas import connect_target, dry_run, execute_insert

df = pd.read_csv('mi_resultado.csv')
engine = connect_target('/tmp/mi_db.sqlite')

# Dry-run
print(dry_run(engine, df, 'mi_tabla'))

# Execute (despues de pedir confirmacion al usuario)
result = execute_insert(engine, df, 'mi_tabla', auto_confirm=True)
print(result)
"
```

## Tipos de datos inferidos

`sql-write` detecta los dtypes de pandas y los mapea al dialecto:

| Pandas dtype | SQLite | Postgres | Snowflake | BigQuery |
|---|---|---|---|---|
| int64 / int32 | INTEGER | BIGINT / INTEGER | NUMBER(38,0) | INT64 |
| float64 / float32 | REAL | DOUBLE PRECISION / REAL | FLOAT | FLOAT64 |
| bool | BOOLEAN | BOOLEAN | BOOLEAN | BOOL |
| datetime64[ns] | TIMESTAMP | TIMESTAMP | TIMESTAMP_NTZ | TIMESTAMP |
| object (str) | TEXT | TEXT | TEXT | STRING |

## Audit log

Ubicación: `~/.agents/audit/sql-write.log` (sobrescribible via env var
`SQL_WRITE_AUDIT_DIR`).

Formato: una línea JSON por escritura. Ejemplo:
```json
{"timestamp": "2026-09-14T18:52:20+00:00", "action": "create+insert",
 "engine": "sqlite", "target": "top_clients_q2_2026",
 "status": "ok", "n_rows": 5, "duration_ms": 39}
```

Rotación automática: cuando el archivo activo supera 1MB, se renombra
a `sql-write.log.1` (el `.10` más viejo se borra). Append-only: nunca
se borran entries manualmente.

## Justificaciones comunes

- **Por qué modo conservador?** Porque el caso de uso del data analyst
  es persistir resultados, no modificar/borrar data existente. DROP/
  UPDATE/DELETE tienen un riesgo inherente que no se justifica para
  el 80% de los casos.
- **Por qué dry-run obligatorio?** Para que el usuario vea el SQL que
  se va a ejecutar y el preview de las filas antes de tocar la DB. Es
  barato (no escribe nada) y previene errores.
- **Por qué audit log append-only?** Para que un manager pueda responder
  "¿quién corrió qué query contra la warehouse y cuándo?". El log
  nunca se borra automáticamente (solo rotación por tamaño).
- **Por qué `auto_confirm=True` requerido?** Para forzar al caller
  (skill o agente) a pedir confirmación al usuario. La skill NO
  decide por sí sola cuándo ejecutar.

## Señales de alerta

- **`BlockedOperationError`**: el SQL contiene una operación destructiva
  (`DROP`, `UPDATE`, etc.). Mostrar al usuario la operación exacta y
  la sugerencia de usar el modo full (ADR-003).
- **`SqlWriteError` con "INSERT fallo"**: la transacción se revirtió.
  Común: constraint violation (PK duplicado, NOT NULL faltante),
  permisos insuficientes, tipo incompatible. Mostrar el mensaje
  original de SQLAlchemy.
- **`auto_confirm=False`**: la skill NO ejecuta. El caller debe pedir
  confirmación primero.
- **Cached value = None**: openpyxl no ejecutó la fórmula. El archivo
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

Criterios de "listo" (ver `docs/prd/sql-write.md`):

- [x] `examples/sql_write_sample/` con CSV de muestra + script de demo.
- [x] `make test-sql-write` ejecuta el demo y valida:
  - 5 filas insertadas en SQLite
  - Audit log tiene la entrada correcta
  - DROP/UPDATE/DELETE/ALTER/GRANT/REVOKE bloqueados con error accionable
- [x] La skill está en `skills/sql-write/SKILL.md` con el template
      de 6 secciones completo.
- [x] `AGENTS.md` actualizado: `sql-analyst` carga `sql-write` SOLO si
      el usuario pide escribir.
- [x] `bin/install.js` corre sin cambios.

## Dependencias

- **sqlalchemy** >= 2.0 — peerDep opcional (ya estaba para sql-cloud-warehouse)
- **pandas** >= 2.0 — peerDep opcional (ya estaba)
- **snowflake-connector-python** + **sqlalchemy-bigquery** + **redshift-connector** — peerDeps opcionales (para cloud warehouses)
- **sqlite3** — stdlib de Python, no requiere instalación

Sin drivers cloud, la skill funciona con SQLite local y cubre el caso
80% (persistir resultados de scripts Python).