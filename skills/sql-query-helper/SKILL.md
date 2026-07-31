---
name: sql-query-helper
description: Provee idiomas SQL según motor (SQLite, Postgres, MySQL, DuckDB) para patrones comunes: top-N por grupo, totales corridos, joins, deduplicación, manejo de nulos. Úsese cuando se escribe cualquier consulta no trivial, o al portar una consulta entre motores.
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

## Lista de verificación de seguridad

- Siempre parametrizar el input del usuario. Nunca formatear con string
  valores dentro del SQL.
- Siempre correr `EXPLAIN` (o `EXPLAIN QUERY PLAN`) para consultas que toquen
  >100k filas.
- Siempre usar `BEGIN; ... COMMIT;` (o `ROLLBACK;`) para trabajo multi-statement.
- Nunca `SELECT *` en una consulta que se vaya a guardar a un archivo —
  listar las columnas.

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "SQL es SQL, MySQL y Postgres son lo mismo." | La sintaxis de window functions y la matemática de fechas difieren lo suficiente como para romper silenciosamente. |
| "Pongo `LIMIT 10` y listo para top-N." | Eso es top-N global, no por grupo. |
| "Uso `SELECT DISTINCT` para deduplicar." | `DISTINCT` colapsa filas en vez de elegir una por clave — semántica distinta. |
| "Formateo con string los valores del WHERE." | Inyección. Usar placeholders `?`. |

## Señales de alerta

- Mezclar motores en la misma consulta (sintaxis de Postgres dentro de una
  conexión MySQL).
- Usar `SELECT *` contra una tabla ancha para "explorar".
- Agregar antes de filtrar.
- Joinear dos columnas de tipos distintos sin `CAST` explícito.
- Input del usuario hardcodeado dentro del string de la consulta.

## Verificación

- [ ] El motor está identificado y enunciado al inicio del trabajo.
- [ ] Todos los CTEs están nombrados por su grano, no por su orden.
- [ ] Las columnas son explícitas, sin `SELECT *`.
- [ ] Los valores provistos por el usuario usan parámetros bindeados, no
  concatenación de strings.
- [ ] `EXPLAIN` revisado para cualquier consulta que toque >100k filas.
