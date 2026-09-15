# Databricks (Spark SQL) dialect coverage review

> **Propósito:** auditar la cobertura que `sql-cloud-warehouse` da al
> dialecto Databricks (Spark SQL) agregado en v0.9.0, identificar gaps
> reales contra los otros dialectos (Snowflake, BigQuery, Redshift),
> y priorizar trabajo futuro. No es una spec nueva — es el review
> prometido en `CHANGELOG.md` como criterio de v1.0.

- **Status:** Review (2026-09-15)
- **Auditado:** `skills/sql-cloud-warehouse/recetas/dialect_snippets.py`
  + `connect.py` + `introspect.py` + tests en `tests/test_sql_cloud_warehouse_dialect.py`
- **Trigger original:** v0.9.0 commit `842dab6 feat(sql-cloud-warehouse):
  soporte para Databricks (Spark SQL)`

## TL;DR

Databricks (Spark SQL) tiene **cobertura básica completa** en los 5
snippets dialecto-aware (DATE_TRUNC, conditional, safe_cast,
current_timestamp, top_n). Los 32 unit tests existentes en
`tests/test_sql_cloud_warehouse_dialect.py` ejercitan los 4 warehouses
en paralelo, asi que Databricks está cubierto por la misma suite que
los otros dialectos. Los gaps reales están en **window functions**,
**QUALIFY** y **PIVOT** — son temas donde Spark SQL diverge de los
otros y ameritan snippets dedicados (no los hay hoy).

## Cobertura actual (qué funciona)

### 5 snippets en `dialect_snippets.py`

| Snippet | Snowflake | BigQuery | Redshift | Databricks | Tests |
|---|---|---|---|---|---|
| `date_trunc` | `'month'` literal | `MONTH` keyword | `'month'` literal | `'month'` literal (igual a Snowflake) | ✅ |
| `conditional` | `IFF` | `IF` | `CASE WHEN` | `IF` (igual a BigQuery) | ✅ |
| `safe_cast` | `TRY_CAST` | `SAFE_CAST` | `TRY_CAST` | `TRY_CAST` (igual a Snowflake) | ✅ |
| `current_timestamp` | `CURRENT_TIMESTAMP()` | `CURRENT_TIMESTAMP()` | `GETDATE()` | `CURRENT_TIMESTAMP()` | ✅ |
| `top_n` | `LIMIT n` | `LIMIT n` | `LIMIT n` | `LIMIT n` | ✅ |

Patrón observado: Databricks se agrupa con Snowflake/Redshift en
3 de 5 snippets y con BigQuery en 1. Ningún caso especial único.
**No hay bugs conocidos en la cobertura actual.**

### Conexión (`connect.py`)

- `_connect_databricks()` arma URL `databricks://token:<TOKEN>@<HOST>?http_path=...`
  con soporte opcional de catalog/schema (Unity Catalog).
- Detecta credenciales faltantes con `MissingCredentialsError` accionable.
- Detecta dep faltante (`databricks-sql-connector` o `databricks-sqlalchemy`)
  con `MissingDependencyError` accionable.
- Tests: `examples/sql_cloud_warehouse_sample/demo_offline.py` ejercita
  el path sin driver real (solo verifica que los errores sean accionables).

### Introspección (`introspect.py`)

- `_detect_default_schema()` devuelve `'default'` para dialectos
  que matcheen `'databricks'`.
- Query `_INTROSPECT_QUERY_CLOUD` usa `information_schema.columns`,
  que **Databricks Unity Catalog expone** (a diferencia de Spark
  puro sin Unity Catalog). Si el cluster NO usa Unity Catalog, la
  query falla — documentado como limitación.

### Identificadores (backticks vs comillas)

Documentado en `SKILL.md` (tabla de "Diferencias de sintaxis clave"):

| Dialecto | Identificadores |
|---|---|
| Snowflake | `"double quotes"` |
| BigQuery | `` `backticks` `` |
| Redshift | `"double quotes"` |
| Databricks | `` `backticks` `` |

**No hay snippet `identifier_quote(name)`** — gap menor. Si el agente
construye queries dinámicamente (con identificadores del schema), tiene
que recordar la regla por dialecto. Agregar un snippet es trivial
(~5 líneas) pero requiere tests nuevos.

## Gaps identificados

### G1. Window functions (LAG, LEAD, ROW_NUMBER, RANK, etc.) — gap real

Sintaxis **idéntica** en los 4 dialectos:

```sql
LAG(amount, 1, 0) OVER (PARTITION BY customer_id ORDER BY date) AS prev_amount
```

No hay diferencia de sintaxis, así que **no requiere snippet dedicado**.
Pero hay un gotcha con `BETWEEN ... AND ...` vs `ROWS BETWEEN`:

```sql
-- ANSI standard (todos los warehouses):
SUM(x) OVER (ORDER BY ts ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)

-- Algunos warehouses aceptan tambien (Spark SQL lo acepta):
SUM(x) OVER (ORDER BY ts RANGE BETWEEN INTERVAL '7' DAY PRECEDING AND CURRENT ROW)
```

`RANGE BETWEEN ... INTERVAL ...` no funciona en todos los warehouses.
El skill NO tiene snippet para window frames; recomienda los snippets
genericos de `sql-query-helper`.

**Recomendación:** no agregar snippet para window frames — son patrones
que el usuario escribe a mano, no construyen dinamicamente. Documentar
en `sql-query-helper/SKILL.md` que `RANGE BETWEEN ... INTERVAL ...`
es Spark-specific.

### G2. QUALIFY clause — gap específico de Spark SQL

```sql
-- Spark SQL: filtrar window functions sin subquery
SELECT customer_id, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY date DESC) AS rn
FROM orders
QUALIFY rn = 1

-- Equivalente en otros dialectos (sin QUALIFY): usar CTE o subquery
```

`QUALIFY` es nativo en Spark SQL desde 3.2+. Snowflake lo agregó
en preview en 2023. BigQuery y Redshift **no lo soportan** (hay que
usar subquery).

**Recomendación:** agregar snippet `qualify_clause(condition)` para
Databricks. Devuelve `QUALIFY <condition>` solo para Databricks;
para los otros dialectos, el agente tiene que traducir a subquery
(no automatico). Tests: 1 happy path + 1 check de no-op en otros
dialectos.

### G3. PIVOT / UNPIVOT — gap complejo

Sintaxis diverge entre dialectos:

```sql
-- Snowflake / Databricks:
SELECT * FROM sales PIVOT (SUM(amount) FOR product IN ('A', 'B', 'C'))

-- BigQuery:
SELECT * FROM sales PIVOT (SUM(amount) FOR product IN ('A', 'B', 'C'))  -- igual a Snowflake desde 2022

-- Redshift: no tiene PIVOT nativo — usar CASE WHEN + GROUP BY
```

**Recomendación:** no agregar snippet para PIVOT — la semántica
divergente entre Redshift y los otros 3 hace que un helper "seguro"
no exista. Si el usuario necesita PIVOT, lo escribe a mano siguiendo
los snippets de `sql-query-helper`.

### G4. identifier_quote(name) — gap trivial

**Recomendación:** agregar como snippet nuevo. Bajo costo, alto valor
(el agente no tiene que recordar la regla por dialecto):

```python
def identifier_quote(name: str, warehouse_type: str) -> str:
    """Devuelve el nombre entre comillas estilo del dialecto."""
    wh = dialect_for(warehouse_type)
    if wh in ("bigquery", "databricks"):
        return f"`{name}`"
    return f'"{name}"'  # Snowflake, Redshift
```

Tests: 4 dialectos × 2 edge cases (nombre con punto, nombre con guion).

### G5. STRING_AGG / LISTAGG / GROUP_CONCAT — gap menor

```sql
-- Snowflake / PostgreSQL / Redshift:
LISTAGG(name, ', ') WITHIN GROUP (ORDER BY name)
-- o equivalente:
STRING_AGG(name, ', ')

-- BigQuery:
STRING_AGG(name, ', ')

-- Databricks:
ARRAY_JOIN(COLLECT_LIST(name), ', ')  -- Spark 3.4+
-- o
CONCAT_WS(', ', COLLECT_LIST(name))   -- equivalente
```

**Recomendación:** no agregar snippet — divergencia real entre
`STRING_AGG` y `ARRAY_JOIN(COLLECT_LIST)`. El usuario lo escribe
a mano si lo necesita.

### G6. NOW() vs CURRENT_TIMESTAMP() — ya cubierto

Ya hay `current_timestamp()` que devuelve la expresión correcta por
dialecto. Verificado en los tests.

### G7. date_add / date_sub / date_diff — no cubiertos

Funciones de aritmética de fechas divergen:

```sql
-- Snowflake / BigQuery / Redshift:
DATEADD(day, 7, date_col)        -- Snowflake, Redshift
DATE_ADD(date_col, INTERVAL 7 DAY)  -- BigQuery
DATEADD('day', 7, date_col)      -- Snowflake string-based

-- Databricks:
DATE_ADD(date_col, 7)             -- Spark 3.x
-- o
date_col + INTERVAL 7 DAYS        -- ANSI
```

**Recomendación:** no agregar — divergencia alta, baja frecuencia.
Si el usuario lo necesita, lo escribe a mano.

## Resumen de recomendaciones

| Gap | Severidad | Recomendación | Esfuerzo |
|---|---|---|---|
| G1. Window frames | baja | Doc en `sql-query-helper` | 30 min |
| G2. QUALIFY | media | Snippet nuevo + 2 tests | 30 min |
| G3. PIVOT | alta divergencia | Dejar como escritura manual | — |
| G4. identifier_quote | media | Snippet nuevo + 8 tests | 30 min |
| G5. STRING_AGG | media divergencia | Dejar como escritura manual | — |
| G7. date_add | baja divergencia | Dejar como escritura manual | — |

**Total para cerrar gaps accionables:** ~1.5 h (G1 doc + G2 + G4
con tests).

## Tests existentes que cubren Databricks hoy

Los 32 tests en `tests/test_sql_cloud_warehouse_dialect.py`
ejercitan los 4 dialectos en cada `@pytest.mark.parametrize`. Databricks
está cubierto por la misma suite — no requiere tests separados.
Correlación con el checklist de cobertura:

- ✅ `date_trunc` (4 dialectos)
- ✅ `conditional` (4 dialectos)
- ✅ `safe_cast` (3 dialectos parametrizados + Databricks en `test_others_use_try_cast`)
- ✅ `current_timestamp` (4 dialectos)
- ✅ `top_n` (4 dialectos)
- ✅ `dialect_for` (lowercase, unsupported, empty)
- ❌ QUALIFY (no existe snippet)
- ❌ identifier_quote (no existe snippet)

## Próximos pasos

1. **Implementar G4 (identifier_quote)** — snippet trivial, alto valor.
   Cambio de ~10 líneas + 8 tests. Cubre un patron real que el
   `sql-analyst` necesita cuando construye queries dinamicamente.
2. **Implementar G2 (QUALIFY)** — snippet pequeño pero util para
   el caso especifico de Spark SQL.
3. **Documentar G1 en `sql-query-helper/SKILL.md`** — nota sobre
   `RANGE BETWEEN ... INTERVAL ...` siendo Spark-specific.
4. **Re-run `make test-unit`** — los tests nuevos viven en el mismo
   archivo, no requiere setup adicional.

**No hacer:** snippets para PIVOT, STRING_AGG, date_add — la divergencia
entre dialectos hace que un helper "seguro" no exista. Esos patrones
los escribe el usuario a mano cuando los necesita.
