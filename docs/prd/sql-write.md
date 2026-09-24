# PRD — `sql-write`

- **Status:** Accepted (2026-09-15)
- **Implementation:** shipped at v0.7.0. Ver [CHANGELOG.md](../../CHANGELOG.md).
- **Owner:** CodeHak (Bastian)
- **ADR relacionado:** [002-end-to-end-delivery](../adr/002-end-to-end-delivery.md)
- **Skills relacionadas:** `sql-analyst` (carga esta solo si el usuario pide escribir), `audit-log` (cuando esté), `schema-mapper`, `query-validation`

## Goal

Que un data analyst pueda **persistir resultados de análisis en una DB**
de manera segura: el output de un script Python (DataFrame con top-100
clientes, segmento agregado, etc.) → INSERT/CREATE en SQLite/Postgres/MySQL/
Snowflake/BigQuery/Redshift, **sin riesgo de perder datos existentes**.

## User story

> Como data analyst en una fintech, terminé un script que calcula el
> "top 100 clientes por revenue Q2 2026". Quiero persistir el resultado
> en una tabla `analytics.top_clients_q2` para que el equipo de pricing
> la consulte mañana vía SQL. Necesito un comando que:
> 1. Me pida confirmación doble antes de escribir (dry-run + ejecutar)
> 2. Valide que la tabla no exista (CREATE TABLE IF NOT EXISTS) o que
>    el INSERT no rompa constraints
> 3. Loguee qué query se ejecutó, cuándo, por quién
> 4. NO me deje hacer DROP/UPDATE/DELETE/TRUNCATE (eso es destructive)

## Modo conservador (v1)

**Operaciones permitidas:**
- `CREATE TABLE IF NOT EXISTS <table> (...)` — crear tabla nueva, no falla si existe
- `INSERT INTO <table> [(cols)] VALUES (...)` — insertar filas nuevas
- `INSERT INTO <table> SELECT ...` — insertar desde query (NO destructivo si SELECT no toca la misma tabla)
- `CREATE INDEX IF NOT EXISTS` — crear indice nuevo
- `CREATE VIEW` — crear vista

**Operaciones BLOQUEADAS (mode conservador):**
- `DROP TABLE`, `DROP DATABASE`, `DROP SCHEMA` — destructivo
- `UPDATE`, `DELETE`, `TRUNCATE` — modifican/borran data existente
- `ALTER TABLE DROP COLUMN`, `ALTER TABLE RENAME` — destructivos
- `GRANT`, `REVOKE` — permisos
- Cualquier query que no sea SELECT/CREATE/INSERT — error accionable

**Operaciones que requieren modo full (fuera de scope v1):**
- DROP TABLE, UPDATE, DELETE, TRUNCATE — necesitan dry-run + rollback
- Migraciones de schema

## Scope in (v1)

- **Inputs**: ruta a un archivo CSV/Parquet, nombre de tabla destino, engine
  (sqlite/postgres/mysql/snowflake/bigquery/redshift), schema opcional.
- **Outputs**:
  - Dry-run: tabla preview con las primeras 5 filas + DDL de la tabla destino
  - Execute: filas insertadas, tiempo de ejecución, confirmación al audit log
  - Validación: chequea que el SQL solo contenga operaciones permitidas
- **Guardrails obligatorios**:
  - **Dry-run primero**: muestra lo que va a pasar ANTES de ejecutar
  - **Doble confirmación**: el usuario debe escribir "yes" dos veces
    (una para dry-run, otra para execute)
  - **Validación estática de SQL**: regex sobre el query parseado para
    detectar operaciones bloqueadas. Si encuentra alguna, rechaza con
    error accionable.
  - **Audit log**: antes de ejecutar, escribe al log quién-cuándo-qué-query.
- **Drivers**: reusa SQLAlchemy (ya está) + drivers cloud (peerDeps
  opcionales de `sql-cloud-warehouse`).
- **Tipos de datos**: detecta tipos del DataFrame (int/float/str/bool/datetime)
  y los mapea al dialecto (BIGINT, FLOAT, VARCHAR, BOOLEAN, TIMESTAMP).

## Scope out (v1, queda como follow-up)

- **Modo full** (DROP/UPDATE/DELETE con rollback script): ADR-003.
- **Bulk upsert** (INSERT ... ON CONFLICT): fuera de scope v1; usa
  `INSERT` simple + warning si la tabla ya tiene PK conflictiva.
- **Migraciones de schema** (ALTER TABLE ADD COLUMN, RENAME): fuera de scope.
- **Transacciones distribuidas** (XA, 2PC): fuera de scope; SQLAlchemy
  hace transacciones locales single-engine.
- **Streaming inserts** (millones de filas en chunks): fuera de scope.
  Si pasa N=10000 filas, log warning. Si pasa N=100000, sugiere `COPY`
  (Postgres) o `bq load` (BigQuery).

## Workflow (las 6 fases de la skill)

1. **Detectar el target**: leer `WAREHOUSE_TYPE` de env o aceptar
   `--engine`. Si es SQLite local, ruta al archivo. Si es cloud,
   reusar `connect_warehouse()` de `sql-cloud-warehouse`.
2. **Cargar el DataFrame** desde CSV/Parquet/Excel.
3. **Validar el SQL propuesto** (estático):
   - Parsear el SQL a tokens.
   - Verificar que la primera keyword es CREATE o INSERT.
   - Verificar que NO contiene DROP/UPDATE/DELETE/TRUNCATE/ALTER/GRANT/REVOKE.
   - Si falla, error accionable con la keyword ofensiva.
4. **Dry-run obligatorio**: ejecutar `EXPLAIN` o equivalente (lo que
   soporte el engine) + mostrar preview de las primeras 5 filas que se
   insertarían. Pedir confirmación #1.
5. **Execute**: INSERT real (o CREATE + INSERT si la tabla no existe).
   Usar transacción SQLAlchemy. Si falla, rollback automático. Pedir
   confirmación #2 antes de empezar.
6. **Audit log + reporte**: escribe al log la query, hora, filas
   insertadas, tiempo. Output al usuario con métricas.

## Recetas iniciales (snippets pre-aprobados)

- `validate_sql(sql) -> (bool, str)` — estático, rechaza operaciones
  bloqueadas
- `load_dataframe(path, file_type) -> pd.DataFrame` — desde CSV/Parquet/Excel
- `connect_engine(target) -> Engine` — wrapper sobre `connect_warehouse`
  + soporte SQLite local
- `dry_run(engine, df, table_name, schema=None) -> dict` — preview + DDL
- `execute_insert(engine, df, table_name, schema=None) -> dict` — INSERT
  con transacción
- `audit_log(action, sql, n_rows, duration_ms) -> None` — escribe al
  log JSON append-only **transversal** (default `~/.agents/audit/events.jsonl`,
  override por env var `AUDIT_LOG_DIR`; mismo archivo que `audit-log`)

## Verificación (criterios de "listo")

- [ ] `examples/sql_write_sample/` con un CSV de muestra + script de
      demo que:
  - Carga el CSV
  - Valida el SQL (pasa porque es solo INSERT)
  - Dry-run con preview
  - Execute con confirmación (auto-confirm en el demo via flag)
  - Log al audit trail
- [ ] `make test-sql-write` ejecuta el demo y verifica:
  - Las filas se insertaron en SQLite
  - El audit log tiene la entrada
  - Un test explícito intenta ejecutar un DROP y falla con error accionable
- [ ] La skill está en `skills/sql-write/SKILL.md` con el template
      de 6 secciones completo.
- [ ] `AGENTS.md` actualizado: `sql-analyst` carga `sql-write` SOLO si
      el usuario pide escribir (con guardrails explícitos).
- [ ] `bin/install.js` corre sin cambios.

## Estimación

- Specs + sample: 30 min (hecho).
- Implementación SKILL.md + recetas: 4-5 horas.
- Demo + tests con guardrails: 1.5-2 horas.
- Actualización AGENTS.md: 30 min.

**Total: ~7-8 horas de código + tests.**