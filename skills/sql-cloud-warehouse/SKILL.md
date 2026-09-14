---
name: sql-cloud-warehouse
description: Conecta el toolkit a Snowflake, BigQuery o Redshift via SQLAlchemy + driver oficial, con snippets SQL dialecto-aware (DATE_TRUNC, IFF/IF/CASE, TRY_CAST/SAFE_CAST). Usese cuando el `sql-analyst` reciba un target cloud en vez de SQLite/Postgres/MySQL/DuckDB local. Solo lectura (SELECT); INSERT/UPDATE/DDL quedan fuera de scope v1. Las deps cloud (snowflake-connector-python, sqlalchemy-bigquery, sqlalchemy-redshift) son peerDeps OPCIONALES — la skill emite error accionable con `pip install` si faltan.
---

# SQL Cloud Warehouse

Apunta el flujo de `sql-analyst` a un data warehouse cloud (Snowflake,
BigQuery, Redshift) usando las mismas credenciales que ya pasaste via
`.env` o vault.

## Descripcion general

A diferencia de `sql-analyst` (que apunta a SQLite/Postgres/MySQL/DuckDB
locales), esta skill:

- Construye un SQLAlchemy Engine apuntando al warehouse cloud.
- Provee snippets SQL que saben la diferencia entre los 3 dialectos
  (ej. Snowflake usa `IFF(cond, a, b)`, BigQuery usa `IF(...)`, Redshift
  usa `CASE WHEN` — el toolkit NO mezcla sintaxis).
- Mantiene la misma forma de output que `schema-mapper` para que el
  resto del flujo (query → validate) funcione igual.
- **Solo lectura**: SELECT unicamente. INSERT/UPDATE/DDL quedan
  explicitamente fuera de scope v1 (si mas adelante hace falta, va como
  bloque explicito aprobado con guardrails extras).

## Cuando usar

Invocar esta skill cuando el pedido matchee con alguno de:

- "Tengo un proyecto Snowflake / BigQuery / Redshift con N tablas.
  Dame el top 10 clientes por revenue."
- "Conectate a este warehouse y mapéame el schema."
- "Escribime esta query en dialecto BigQuery (con backticks y SAFE_CAST)."
- "Validá que esta query no escanee más de 1TB antes de correrla."

**No** invocar cuando:

- El target es SQLite/Postgres/MySQL/DuckDB local → `sql-analyst` solo.
- El usuario quiere escribir datos (INSERT/UPDATE/CREATE TABLE) → fuera
  de scope v1. Si lo pide, escalar a la siguiente sesion (ADR-002).
- El warehouse es Databricks SQL → fuera de scope v1, queda como follow-up.

## Flujo de trabajo

1. **Detectar el target**: leer `WAREHOUSE_TYPE` de env
   (`snowflake` | `bigquery` | `redshift`). Si no esta, inferir del
   connection string o pedir al usuario explicitamente.
2. **Verificar credenciales** y construir el Engine SQLAlchemy:
   - Snowflake: `SNOWFLAKE_ACCOUNT/USER/PASSWORD/WAREHOUSE/DATABASE`
     (opcional `SNOWFLAKE_SCHEMA`).
   - BigQuery: `WAREHOUSE_PROJECT` + `WAREHOUSE_DATASET`
     (o `GOOGLE_APPLICATION_CREDENTIALS` apuntando al JSON de service
     account).
   - Redshift: `REDSHIFT_HOST/PORT/USER/PASSWORD/DATABASE`.
3. **Test de conexion**: ejecutar `SELECT 1` para validar que el engine
   responde antes de seguir. Si falla, mensaje accionable especificando
   que env var o dep falta.
4. **Introspeccionar schema**: `introspect_schema(engine, schema=...)`
   devuelve `{warehouse, schema, tables: {<table>: {columns: [...]}}}`
   en el mismo formato que `schema-mapper`.
5. **Seleccionar tablas candidatas + JOIN paths**: aplicar la heuristica
   del `schema-mapper` existente sobre el output del paso 4.
6. **Escribir query dialecto-aware** usando los snippets de
   `dialect_snippets.py` (ver tabla de diferencias abajo).
7. **Validar query** con `validate_query(query)` (estatico: parentesis
   balanceados, comillas) y `explain_query(engine, query)` cuando el
   warehouse lo soporte (Snowflake/Redshift; BigQuery requiere cliente
   nativo).
8. **Ejecutar query** con `engine.connect()` + `pd.read_sql()`. Output
   en DataFrame pandas + metadata (bytes scanned para BigQuery, credits
   para Snowflake) cuando aplique.

## Recetas pre-aprobadas (importables)

```python
import sys
sys.path.insert(0, "ruta/al/repo")
from skills_loader import load_skill_packages
load_skill_packages("skills")

from sql_cloud_warehouse.recetas import (
    connect_warehouse, test_connection,
    introspect_schema,
    date_trunc, conditional, current_timestamp, safe_cast,
    validate_query, explain_query,
    MissingCredentialsError, MissingDependencyError,
)
```

Las recetas son funciones puras (sin estado) y la mayoria NO requiere
conexion activa (los snippets dialecto-aware son solo strings). La
introspeccion y los connects requieren driver instalado + credenciales
validas.

## Diferencias de sintaxis clave

| Concepto | Snowflake | BigQuery | Redshift |
|----------|-----------|----------|----------|
| Condicional | `IFF(cond, a, b)` | `IF(cond, a, b)` | `CASE WHEN cond THEN a ELSE b END` |
| Truncar fecha | `DATE_TRUNC('month', col)` | `DATE_TRUNC(col, MONTH)` | `DATE_TRUNC('month', col)` |
| Cast seguro | `TRY_CAST(x AS TYPE)` | `SAFE_CAST(x AS TYPE)` | `TRY_CAST(x AS TYPE)` |
| Current ts | `CURRENT_TIMESTAMP()` | `CURRENT_TIMESTAMP()` | `GETDATE()` |
| LIMIT | `LIMIT n` | `LIMIT n` | `LIMIT n` |
| Identificadores | comillas dobles | backticks | comillas dobles |

`dialect_snippets.py` encapsula las 4 primeras en funciones puras. **Usa
esas funciones SIEMPRE que armes una query** — el riesgo real es
copiar-pegar una query de StackOverflow en dialecto equivocado y
gastar credits del warehouse antes de descubrir el error.

## Credenciales

- **Sin secrets hardcodeados**: las credenciales van en `.env` (local) o
  en el vault de la empresa. Nunca en el codigo ni en el repo.
- **Variables requeridas** (ver tabla arriba).
- **`.env.example`** en este directorio documenta las variables por
  warehouse con placeholders (`SNOWFLAKE_ACCOUNT=xxx`).
- **Service accounts** (BigQuery): el JSON va en una ruta local, NO en
  el repo. La env var `GOOGLE_APPLICATION_CREDENTIALS` apunta al path.

## Senales de alerta

- `MissingCredentialsError`: el usuario no configuro las env vars.
  Mostrar el mensaje completo (lista que vars faltan) y donde van en
  `.env.example`.
- `MissingDependencyError`: el driver cloud no esta instalado. Mostrar
  el comando `pip install ...` exacto. NO intentar instalarlo tu mismo
  (peerDep opcional, el usuario decide).
- `OperationalError` con "no such table" tras introspect: el schema
  pasado no existe en el warehouse. Listar los schemas disponibles con
  `SHOW SCHEMAS` (Snowflake) o equivalente.
- Query corre OK pero devuelve 0 filas: chequea el filtro WHERE, el
  warehouse puede tener timezone distinto al local.
- Bytes scanned (BigQuery) > 100GB: warning automatico antes de cobrar.

## Verificacion

Criterios de "listo" (ver `docs/prd/sql-cloud-warehouse.md`):

- [x] Cada warehouse tiene un script de demo que falla con mensaje
      accionable si la credencial o la dep faltan.
- [x] `make test-snowflake`, `make test-bigquery`, `make test-redshift`
      ejecutan los demos (skipped por default si no hay credenciales).
- [x] `make test-sql-cloud-offline` corre los snippets + validate sin
      necesitar credenciales (smoke test puro).
- [x] La skill esta en `skills/sql-cloud-warehouse/SKILL.md` con el
      template de 6 secciones completo.
- [x] `AGENTS.md` actualizado: `sql-analyst` carga `sql-cloud-warehouse`
      ANTES de `sql-query-helper` cuando target es uno de los 3.
- [x] `package.json`: las 3 deps declaradas como peerDeps opcionales.
- [x] `bin/install.js` corre sin cambios.

## Dependencias

| Dep | Tipo | Tamano | Cuando se necesita |
|---|---|---|---|
| `sqlalchemy` >= 2.0 | obligatoria | ~5 MB | siempre |
| `snowflake-connector-python` | peerDep opcional | ~50 MB | solo si target=Snowflake |
| `sqlalchemy-bigquery` + `google-cloud-bigquery` | peerDep opcional | ~30 MB | solo si target=BigQuery |
| `sqlalchemy-redshift` + `redshift-connector` | peerDep opcional | ~20 MB | solo si target=Redshift |

El usuario instala solo la(s) que use. La skill falla con `MissingDependencyError`
y un `pip install <paquete>` accionable si no esta.