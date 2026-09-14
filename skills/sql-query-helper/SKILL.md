---
name: sql-query-helper
description: Provee idiomas SQL según motor (SQLite, Postgres, MySQL, DuckDB) para patrones comunes: top-N por grupo, totales corridos, window frames (LAG/LEAD), CTEs recursivas, EXISTS vs IN, joins, deduplicación, manejo de nulos, lectura de EXPLAIN. Úsese cuando se escribe cualquier consulta no trivial, se porta entre motores, o se diagnostica una consulta lenta.
---

# SQL Query Helper

Una referencia de idiomas según motor. Léase una vez por consulta, elegir el
motor correcto, usar el idioma que corresponda.

## Descripción general

Postgres, MySQL, SQLite y DuckDB comparten la mayor parte de SQL pero
discrepan en: disponibilidad de window functions, funciones de fecha, cláusula
`FILTER`, `ON CONFLICT`, y funciones JSON. Esta skill es la fuente de verdad
para elegir el idioma correcto en el motor destino del usuario.

## Cuándo usar

- El usuario quiere una consulta no trivial (joins, windows, agregaciones).
- El usuario está portando una consulta entre motores.
- El usuario no está seguro de para qué motor está escribiendo.
- La consulta toca más de una tabla.

No **usar** cuando:

- La consulta es trivial (`SELECT col FROM t WHERE id = ?`).
- El usuario quiere los datos, no el SQL — escribir el SQL, correrlo,
  pasarle el resultado a `reporting-analyst`.

## Detección de motor

Preguntarle al usuario una vez al inicio de la sesión. Orden por defecto:
**SQLite > DuckDB > Postgres > MySQL**. Mantener la respuesta en el contexto
de la conversación; no re-preguntar por cada consulta.

## Idiomas comunes

### Top-N por grupo

**Postgres / DuckDB / SQLite ≥ 3.25 / MySQL 8+** (window functions disponibles):

```sql
WITH ranked AS (
  SELECT
    <cols>,
    ROW_NUMBER() OVER (PARTITION BY <group_col> ORDER BY <order_col> DESC) AS rn
  FROM <table>
)
SELECT <cols>
FROM ranked
WHERE rn <= :n;
```

**MySQL 5.x o SQLite < 3.25** (sin window functions): usar subquery
correlacionada.

```sql
SELECT t.*
FROM <table> t
WHERE (
  SELECT COUNT(*) FROM <table> t2
  WHERE t2.<group_col> = t.<group_col> AND t2.<order_col> > t.<order_col>
) < :n;
```

### Total corrido

**Todos los motores con windows** (Postgres, DuckDB, MySQL 8+, SQLite ≥ 3.25):

```sql
SELECT
  <group_col>,
  <order_col>,
  <value_col>,
  SUM(<value_col>) OVER (
    PARTITION BY <group_col>
    ORDER BY <order_col>
    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
  ) AS total_corrido
FROM <table>;
```

### Métrica por fila y luego agregado por grupo (descomposición con CTE)

Todos los motores:

```sql
WITH row_metrics AS (
  SELECT
    <key_cols>,
    <metric_a> AS a,
    <metric_b> AS b
  FROM <table>
),
group_agg AS (
  SELECT
    <key_cols>,
    AVG(a) AS avg_a,
    SUM(b) AS sum_b
  FROM row_metrics
  GROUP BY <key_cols>
)
SELECT *
FROM group_agg
ORDER BY <key_cols>;
```

### Deduplicación — mantener el último por clave

```sql
-- Todos los motores excepto MySQL
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY <key> ORDER BY <updated_at> DESC) AS rn
  FROM <table>
)
SELECT <cols_excluyendo_rn>
FROM ranked
WHERE rn = 1;
```

MySQL 5.x:

```sql
SELECT t.*
FROM <table> t
JOIN (
  SELECT <key>, MAX(<updated_at>) AS max_updated
  FROM <table> GROUP BY <key>
) latest USING (<key>, <updated_at>);
```

### Manejo de nulos — `COALESCE` y `NULLIF`

Todos los motores: idéntico.

```sql
SELECT
  COALESCE(<col>, 0) AS <col>_cero,
  NULLIF(<col>, 0)   AS <col>_no_cero
FROM <table>;
```

### Casting de strings a numérico

```sql
-- Todos los motores
CAST(NULLIF(<col>, '') AS DOUBLE)  -- DuckDB / MySQL
CAST(NULLIF(<col>, '') AS NUMERIC) -- Postgres
CAST(NULLIF(<col>, '') AS REAL)    -- SQLite
```

### Aritmética de fechas

| Operación | Postgres | MySQL | SQLite | DuckDB |
|---|---|---|---|---|
| Ahora | `NOW()` | `NOW()` | `CURRENT_TIMESTAMP` | `NOW()` |
| Diferencia en días entre d1, d2 | `d1 - d2` | `DATEDIFF(d1, d2)` | `julianday(d1) - julianday(d2)` | `d1 - d2` |
| Truncar a mes | `date_trunc('month', d)` | `DATE_FORMAT(d, '%Y-%m-01')` | `date(d, 'start of month')` | `date_trunc('month', d)` |

### `FILTER` (Postgres / DuckDB solamente)

```sql
SELECT
  <group_col>,
  COUNT(*) FILTER (WHERE <cond>) AS cuenta_cond,
  SUM(<col>) FILTER (WHERE <other_cond>) AS suma_otra_cond
FROM <table>
GROUP BY <group_col>;
```

MySQL / SQLite: usar `SUM(CASE WHEN <cond> THEN 1 ELSE 0 END)` en su lugar.

### Upsert (`ON CONFLICT` / `ON DUPLICATE KEY`)

Postgres / SQLite / DuckDB:

```sql
INSERT INTO <table> (<cols>) VALUES (<vals>)
ON CONFLICT (<key>) DO UPDATE SET <col> = EXCLUDED.<col>;
```

MySQL:

```sql
INSERT INTO <table> (<cols>) VALUES (<vals>)
ON DUPLICATE KEY UPDATE <col> = VALUES(<col>);
```

### Agregación JSON

Postgres: `jsonb_object_agg(<k>, <v>)`.
MySQL 8+: `JSON_OBJECTAGG(<k>, <v>)`.
DuckDB: `to_json(<map>)`.
SQLite: `json_group_object(<k>, <v>)` (requiere la extensión JSON1).

### Window frames entre filas adyacentes — `LAG`, `LEAD`, `FIRST_VALUE`, `LAST_VALUE`

**Postgres / DuckDB / MySQL 8+ / SQLite ≥ 3.25**:

```sql
-- Valor de la fila anterior dentro del grupo
SELECT
  <group_col>,
  <order_col>,
  <value_col>,
  LAG(<value_col>, 1)  OVER (PARTITION BY <group_col> ORDER BY <order_col>) AS val_prev,
  LEAD(<value_col>, 1) OVER (PARTITION BY <group_col> ORDER BY <order_col>) AS val_next,
  <value_col> - LAG(<value_col>, 1) OVER (PARTITION BY <group_col> ORDER BY <order_col>) AS delta
FROM <table>;

-- Primer y último valor de la partición (útil para normalización min-max)
SELECT
  <group_col>,
  <order_col>,
  <value_col>,
  FIRST_VALUE(<value_col>) OVER (PARTITION BY <group_col> ORDER BY <order_col>) AS primero,
  LAST_VALUE(<value_col>)  OVER (
    PARTITION BY <group_col> ORDER BY <order_col>
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
  ) AS ultimo
FROM <table>;
```

Casos de uso típicos:
- "Compará este mes contra el anterior" → `value - LAG(value, 1)`.
- "Cuánto falta para el pico del grupo" → `LAST_VALUE - value`.
- "Tasa de cambio porcentual mes a mes" → `(value - LAG(value, 1)) / NULLIF(LAG(value, 1), 0) * 100`.

**SQLite < 3.25 / MySQL 5.x**: no soportan `LAG`/`LEAD` directamente. Usar
subquery correlacionada:

```sql
SELECT
  t1.<group_col>,
  t1.<order_col>,
  t1.<value_col>,
  (SELECT t2.<value_col>
   FROM <table> t2
   WHERE t2.<group_col> = t1.<group_col>
     AND t2.<order_col>  < t1.<order_col>
   ORDER BY t2.<order_col> DESC LIMIT 1) AS val_prev
FROM <table> t1;
```

### `WITH RECURSIVE` — jerarquías y series

**Postgres / SQLite / DuckDB / MySQL 8+** (todos lo soportan; la sintaxis es
idéntica):

```sql
-- Serie de fechas (1 fila por día entre dos extremos)
WITH RECURSIVE dates(d) AS (
  SELECT DATE '2024-01-01'           -- ancla
  UNION ALL
  SELECT d + INTERVAL 1 DAY          -- recursión
  FROM dates
  WHERE d < DATE '2024-12-31'        -- terminación (CRÍTICO para no loop infinito)
)
SELECT d FROM dates;

-- Jerarquía de empleados → manager (Postgres / DuckDB)
WITH RECURSIVE org AS (
  SELECT id, name, manager_id, 0 AS depth, ARRAY[id] AS path
  FROM employees
  WHERE manager_id IS NULL            -- raíz
  UNION ALL
  SELECT e.id, e.name, e.manager_id, org.depth + 1, org.path || e.id
  FROM employees e
  JOIN org ON e.manager_id = org.id   -- siguiente nivel
)
SELECT * FROM org ORDER BY depth, path;
```

Notas:
- El **ancla** es la fila raíz (sin recursion previa). La **recursión**
  referencia el mismo CTE.
- El `WHERE` en la recursión es obligatorio para evitar loops infinitos.
- En Postgres, podés limitar la profundidad con `depth < N` para
 防御ar contra jerarquías cíclicas accidentalmente.
- En MySQL 8+ el default `cte_max_recursion_depth` es 1000; subilo con
  `SET cte_max_recursion_depth = 10000` si lo necesitás.

Casos de uso típicos:
- Generar serie completa de fechas (calendario) para `LEFT JOIN` después.
- Recorrer jerarquías (org chart, categorías, comentarios threaded).
- Caminos en grafos cuando el motor no tiene graph extensions.

### `EXISTS` vs `IN` — reescritura para semi-joins

`IN` y `EXISTS` son **casi** equivalentes pero difieren en presencia de NULLs
y en cómo el motor los optimiza:

```sql
-- Semi-join clásico: clientes que tienen al menos una orden
-- IN (válido salvo NULL en la subquery)
SELECT c.*
FROM customers c
WHERE c.id IN (SELECT o.customer_id FROM orders o);

-- EXISTS (más seguro, el motor lo reescribe a semi-join en Postgres/DuckDB)
SELECT c.*
FROM customers c
WHERE EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);

-- Anti-join: clientes SIN órdenes
-- NUNCA usar NOT IN con NULLs (devuelve 0 filas silenciosamente)
-- Mal:
SELECT c.* FROM customers c WHERE c.id NOT IN (SELECT o.customer_id FROM orders o);
-- Bien (LEFT JOIN):
SELECT c.*
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE o.id IS NULL;
-- Bien (NOT EXISTS):
SELECT c.*
FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id);
```

Reglas de dedo:

| Situación | Usar |
|---|---|
| Semi-join, sin NULLs en la subquery | `IN` o `EXISTS` (equivalentes) |
| Semi-join, la subquery puede tener NULLs | `EXISTS` (NULL-safe) |
| Anti-join | `NOT EXISTS` o `LEFT JOIN ... WHERE IS NULL` — **nunca** `NOT IN` |
| Subquery grande, semi-join | `EXISTS` (el motor lo reescribe a semi-join antes) |
| Test de membresía contra lista hardcoded | `IN (...)` con literales |

### Lectura de `EXPLAIN` por motor — qué nodos buscar

`EXPLAIN` te dice qué piensa hacer el motor. Antes de optimizar, **leélo**:

**Postgres** (`EXPLAIN (ANALYZE, BUFFERS)`):

```
Seq Scan on orders  (cost=0.00..15234.00 rows=500000 width=80)
                    (actual time=0.01..450.00 rows=500000 loops=1)
  Buffers: shared hit=4321
```

- `Seq Scan` → escaneo completo. Sospechoso si la tabla tiene índice
  relevante.
- `Index Scan` / `Index Only Scan` → usa índice. "Only" significa que la
  consulta no toca la tabla (mejor).
- `cost=0.00..15234.00` → estimación del optimizador.
- `actual time=0.01..450.00` → tiempo real medido. Diferencias grandes
  entre `rows` estimado y `actual rows` = mala estimación de
  cardinalidad.
- `Buffers: shared hit=N` → páginas leídas de caché. `read` = disco.

**MySQL** (`EXPLAIN FORMAT=TRADITIONAL`):

```
table  type     key        rows    Extra
orders ALL      NULL       500000  Using filesort
```

- `type=ALL` → full table scan (malo).
- `type=const` / `eq_ref` / `ref` / `range` / `index` → bueno (mejor en
  ese orden).
- `Extra: Using filesort` / `Using temporary` → operaciones costosas;
  suelen mejorar con un índice que cubra el `ORDER BY`/`GROUP BY`.

**SQLite** (`EXPLAIN QUERY PLAN`):

```
SCAN orders
USE TEMP B-TREE FOR ORDER BY
```

- `SCAN <tabla>` → full scan.
- `SEARCH <tabla> USING INDEX <idx> (...)` → usa índice.
- `USE TEMP B-TREE FOR ...` → ordenamiento en memoria, posible swap a
  disco en tablas grandes.

**DuckDB** (`EXPLAIN ANALYZE`):

```
UNGROUPED_AGGREGATE
  HASH_GROUP_BY revenue
    PROJECTION
      SEQ_SCAN orders
```

- `SEQ_SCAN` → full scan (DuckDB no usa índice por default; depende de
  min/max expressions para pruning).
- `HASH_GROUP_BY` / `HASH_JOIN` → eficiente a cardinalidad media/alta.
- DuckDB perfila con `PRAGMA enable_profiling;` + `PRAGMA profiling_output`.


## Lista de verificación de seguridad

- Siempre parametrizar el input del usuario. Nunca formatear con string
  valores dentro del SQL.
- Siempre correr `EXPLAIN` (o `EXPLAIN QUERY PLAN`) para consultas que toquen
  >100k filas.
- Siempre usar `BEGIN; ... COMMIT;` (o `ROLLBACK;`) para trabajo multi-statement.
- Nunca `SELECT *` en una consulta que se vaya a guardar a un archivo —
  listar las columnas.
- Para `WITH RECURSIVE`, verificar que el `WHERE` de terminación esté
  presente y que no pueda generar loops infinitos (testear con un dataset
  pequeño).
- Para `LAG`/`LEAD`, confirmar que la columna `ORDER BY` es única dentro
  de la partición; si hay empates, agregar discriminador (ej.
  `ORDER BY <ts>, id`).

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "SQL es SQL, MySQL y Postgres son lo mismo." | La sintaxis de window functions y la matemática de fechas difieren lo suficiente como para romper silenciosamente. |
| "Pongo `LIMIT 10` y listo para top-N." | Eso es top-N global, no por grupo. |
| "Uso `SELECT DISTINCT` para deduplicar." | `DISTINCT` colapsa filas en vez de elegir una por clave — semántica distinta. |
| "Formateo con string los valores del WHERE." | Inyección. Usar placeholders `?`. |
| "`NOT IN` con subquery está bien." | Si la subquery devuelve NULL, el resultado entero queda vacío silenciosamente. Usar `NOT EXISTS` o `LEFT JOIN`. |
| "`WITH RECURSIVE` es para árboles, no me sirve." | También genera series de fechas y rangos completos sin necesidad de una tabla calendario. |
| "`LAG`/`LEAD` se puede reemplazar con subquery correlacionada." | Sí, pero a 1M filas la subquery es O(n²); `LAG`/`LEAD` es O(n) con window. |
| "EXPLAIN ya lo vi, dice 'seq scan', es lo normal." | `Seq Scan` sobre una tabla con índice relevante es señal de query rewriting o `ANALYZE` desactualizado. Nunca lo aceptes sin chequear. |

## Señales de alerta

- Mezclar motores en la misma consulta (sintaxis de Postgres dentro de una
  conexión MySQL).
- Usar `SELECT *` contra una tabla ancha para "explorar".
- Agregar antes de filtrar.
- Joinear dos columnas de tipos distintos sin `CAST` explícito.
- Input del usuario hardcodeado dentro del string de la consulta.
- `NOT IN (subquery)` sin verificar que la subquery no devuelve NULLs.
- `WITH RECURSIVE` sin `WHERE` de terminación → loop infinito que tira el
  motor.
- `LAG`/`LEAD` sobre una partición con empates en `ORDER BY` → valores no
  deterministas entre corridas.

## Verificación

- [ ] El motor está identificado y enunciado al inicio del trabajo.
- [ ] Todos los CTEs están nombrados por su grano, no por su orden.
- [ ] Las columnas son explícitas, sin `SELECT *`.
- [ ] Los valores provistos por el usuario usan parámetros bindeados, no
  concatenación de strings.
- [ ] `EXPLAIN` revisado para cualquier consulta que toque >100k filas.
