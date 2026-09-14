# PRD — `sql-cloud-warehouse`

- **Status:** Draft → Ready para implementar tras ADR-001 aceptado
- **Owner:** CodeHak (Bastian)
- **ADR relacionado:** [001-portable-day1](../adr/001-portable-day1.md)
- **Skills relacionadas:** `sql-analyst` (carga esta antes), `schema-mapper`, `sql-query-helper`, `query-validation`

## Goal

Que un data analyst nuevo pueda apuntar el `sql-analyst` a una instancia de
**Snowflake, BigQuery o Redshift** usando credenciales del vault/`.env`,
y obtener el mismo flujo de trabajo que ya tiene con sqlite/postgres/mysql/duckdb:
mapeo de schema → query → validación, sin tener que aprender las diferencias
de dialecto a mano.

## User story

> Como data analyst nuevo en una fintech chilena, me pasan acceso a un
> proyecto de BigQuery con 200 tablas y me piden "top 10 clientes por
> revenue Q2 2026". Necesito un comando que: detecte que el target es
> BigQuery, cargue el dialecto correcto, mapee las 200 tablas y me diga
> cuáles son candidatas (clientes, transacciones, fechas), arme el JOIN
> path, escriba la query en dialecto BigQuery (con `SAFE_CAST`,
> backticks, `DATE_TRUNC` correcto), la valide, y la ejecute. Sin tener
> que memorizar las diferencias entre BigQuery SQL y Postgres SQL.

## Scope in (v1)

- **Tres warehouses soportados**: Snowflake, BigQuery, Redshift.
- **Conexión via SQLAlchemy + driver oficial**:
  - Snowflake → `snowflake-connector-python`
  - BigQuery → `google-cloud-bigquery` (con `sqlalchemy-bigquery`)
  - Redshift → `redshift-connector` (con `sqlalchemy-redshift`)
- **Credenciales via `os.environ`**: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
  `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`;
  equivalentes para BigQuery y Redshift. Sin secrets hardcodeados.
- **Mapeo de schema**: reutilizar `schema-mapper` adaptando el método de
  introspección (BigQuery expone `INFORMATION_SCHEMA.COLUMNS` con metadata
  extra como `description`; Snowflake usa `SHOW COLUMNS`; Redshift usa
  `pg_catalog`).
- **Query helper con dialecto-aware**: reutilizar `sql-query-helper`
  extendiendo con snippets específicos por warehouse.
- **Validación**: reutilizar `query-validation` (es dialecto-agnostic).
- **Solo lectura**: SELECT únicamente. INSERT/UPDATE/DDL quedan
  explícitamente fuera de scope.

## Scope out (v1, queda como follow-up)

- **Databricks SQL**: queda como ADR-002 si hay demanda.
- **Escritura/DDL**: si más adelante hace falta, va como bloque
  explícito aprobado con guardrails extras.
- **Streaming results >1GB**: warning + sugerencia de muestreo o
  export a Parquet.
- **OAuth/Service Account flow automático**: v1 usa credenciales
  estáticas en env. OAuth2 + ADC queda como follow-up.
- **Costo / bytes scanned** (BigQuery): exponer como metadata en el
  output, sin optimizador automático.

## Workflow (las 6 fases de la skill)

1. **Detección del target**: leer `WAREHOUSE_TYPE` de env (`snowflake` |
   `bigquery` | `redshift`). Si no está, inferir del connection string o
   pedir al usuario explícitamente.
2. **Construcción del engine SQLAlchemy**: dispatch según `WAREHOUSE_TYPE`.
   Test de conexión (`SELECT 1`) antes de seguir. Si falla, mensaje de
   error accionable (qué variable de env falta).
3. **Mapeo de schema** (reusa `schema-mapper`): introspeccionar todas las
   tablas del schema activo. Para BigQuery, usar
   `INFORMATION_SCHEMA.COLUMNS`; para Snowflake, `SHOW COLUMNS IN SCHEMA`;
   para Redshift, `pg_catalog.pg_tables` + `pg_attribute`. Output en el
   mismo formato JSON que `schema-mapper`.
4. **Selección de tablas candidatas + JOIN paths**: igual que
   `schema-mapper` — usar heurística de nombres (cliente, customer,
   user, transaction, sale, order) + Foreign Keys detectadas.
5. **Query helper dialecto-aware**: snippets pre-aprobados por warehouse:
   - **Snowflake**: `DATE_TRUNC('month', col)`, `IFF(cond, a, b)`,
     backticks opcionales.
   - **BigQuery**: `DATE_TRUNC(col, MONTH)`, `IF(cond, a, b)`,
     backticks obligatorios, `SAFE_CAST` para type casting.
   - **Redshift**: `DATE_TRUNC('month', col)`, `CASE WHEN`, backticks
     opcionales, `GETDATE()`.
   Marcar las diferencias explícitamente en la skill para que el agente
   no mezcle sintaxis.
6. **Validación + ejecución**: `EXPLAIN`/dry-run cuando el warehouse lo
   soporte (BigQuery sí, Snowflake sí, Redshift limitado). Después
   ejecutar la query. Output en DataFrame pandas + métricas de bytes
   scanned (BigQuery) / credits consumed (Snowflake) cuando aplique.

## Recetas iniciales (snippets pre-aprobados)

- `connect_snowflake() -> Engine`
- `connect_bigquery() -> Engine`
- `connect_redshift() -> Engine`
- `bigquery_dialect_snippets() -> dict[str, str]`
- `snowflake_dialect_snippets() -> dict[str, str]`
- `redshift_dialect_snippets() -> dict[str, str]`
- `introspect_bigquery_schema(engine, project, dataset) -> dict`
- `introspect_snowflake_schema(engine, database, schema) -> dict`
- `introspect_redshift_schema(engine, schema) -> dict`

## Verificación (criterios de "listo")

- [ ] Cada warehouse tiene un script de demo en `examples/` que:
  - Lee credenciales de `.env.example` (placeholders).
  - Ejecuta una query de ejemplo (`SELECT current_timestamp()` o
    equivalente).
  - Falla con mensaje accionable si la credencial falta.
- [ ] `make test-snowflake`, `make test-bigquery`, `make test-redshift`
  ejecutan los demos (skipped por default si no hay credenciales reales).
- [ ] La skill está en `skills/sql-cloud-warehouse/SKILL.md` con el
  template de 6 secciones completo.
- [ ] `AGENTS.md` actualizado: `sql-analyst` carga `sql-cloud-warehouse`
  ANTES de `sql-query-helper` cuando el target es uno de los 3.
- [ ] `package.json`: las 3 deps se declaran como `peerDependencies`
  opcionales con comentario "instala solo el que uses".
- [ ] `bin/install.js` corre sin cambios.

## Estimación

- Specs + demos: 30 min (hecho).
- Implementación SKILL.md + recetas: 4-5 horas (la parte de dialectos
  es la más densa).
- Tests con credenciales mock: 1 hora.
- Actualización AGENTS.md/package.json: 30 min.

**Total: ~6-7 horas de código + tests.**