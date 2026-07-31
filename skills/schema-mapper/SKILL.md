---
name: schema-mapper
description: Auto-descubre el esquema de una base de datos (tablas, columnas, tipos, claves primarias, claves foráneas, índices) y produce un diccionario de datos + guía de join paths. Úsese al explorar una base de datos desconocida antes de escribir SQL, al documentar un esquema, o cuando se pregunte "¿cómo joineo X con Y?". Se usa junto a sql-analyst como el paso previo a escribir.
---

# Schema Mapper

El paso previo a escribir de `sql-analyst`. Antes de escribir una consulta,
conocer el esquema: qué tablas existen, cuál es su grano, qué claves joinean
con cuáles, y qué columnas admiten nulo. Esta skill automatiza el descubrimiento
para que el agente no re-describa tablas a mano en cada sesión.

Esta skill **complementa** a `sql-query-helper` (idiomas para escribir) y
`query-validation` (revisión post-escritura). Corre **antes** de cualquiera de
las dos.

## Descripción general

Un schema mapper recorre el catálogo de metadatos de la base (sin tocar filas
de datos), registra las columnas y tipos de cada tabla, identifica claves
primarias (PK) y claves foráneas (FK), índices y grano, y luego produce:

1. Un **diccionario de datos** (markdown) — una fila por columna por tabla,
   con tipo, nulable, rol inferido (PK, FK, dimensión, medida, tiempo, otro).
2. Una **guía de join paths** (markdown) — para cualquier par de tablas
   nombrado por el usuario, la secuencia mínima de JOINs entre ellas.
3. Un **boceto de ERD** (bloque Mermaid `erDiagram`) — embebible en markdown.

La salida se guarda en una ruta nombrada por el usuario, por defecto
`./schema/` junto al directorio de trabajo.

## Cuándo usar

- La base es desconocida (primera sesión, primer pedido del día, o fuente de
  datos nueva).
- El usuario pregunta "¿qué tablas tenemos?" o "¿cómo joineo X con Y?".
- El usuario pide explícitamente documentación del esquema o un ERD.
- La consulta toca más de dos tablas y los joins no son obvios.

No **usar** cuando:

- El esquema ya es conocido y las claves de join son obvias para quien
  escribe.
- La consulta es de una sola tabla sin joins.
- Los datos son un CSV o Parquet → usar `csv-profiler` en su lugar.
- El usuario quiere la salida de la consulta, no entender el esquema —
  preguntar si quiere primero el diccionario o solo la respuesta.

## Flujo de trabajo

### 1. Confirmar la conexión y el alcance

Antes de cualquier consulta, enunciar en voz alta:

- Motor y versión de la base (SQLite ≥ 3.16, Postgres ≥ 10, MySQL ≥ 5.7,
  DuckDB ≥ 0.5).
- Schema(s) destino: `public` para Postgres, DB por defecto para SQLite, etc.
- Alcance: **todas las tablas** del esquema, o un subconjunto nombrado
  (`fct_*`, `dim_*`, `stg_*`, o tablas específicas que nombró el usuario).

Si el usuario solo quiere el vecindario de una tabla, decirlo de entrada —
ahorra trabajo después.

### 2. Extraer metadatos (consultas específicas del motor)

Usar `information_schema` (o equivalente nativo del motor) para obtener los
metadatos **sin escanear filas de datos**. Adaptar la consulta al motor
detectado en el paso 1.

#### SQLite

```sql
SELECT m.name AS table_name,
       p.cid AS ordinal,
       p.name AS column_name,
       p.type AS data_type,
       p.[notnull] AS not_null,
       p.pk AS is_pk,
       p.dflt_value AS default_value
FROM sqlite_master m
JOIN pragma_table_info(m.name) p
WHERE m.type = 'table'
  AND m.name NOT LIKE 'sqlite_%'
ORDER BY m.name, p.cid;
```

Descubrimiento de FK (SQLite ≥ 3.6):
```sql
SELECT m.name AS table_name,
       f.[from] AS from_col,
       f.[table] AS ref_table,
       f.[to]   AS ref_col
FROM sqlite_master m, pragma_foreign_key_list(m.name) f
WHERE m.type = 'table'
ORDER BY m.name;
```

#### Postgres

```sql
SELECT c.table_schema, c.table_name, c.ordinal_position, c.column_name,
       c.data_type, c.is_nullable, c.column_default
FROM information_schema.columns c
WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')
  AND c.table_schema = :schema
ORDER BY c.table_name, c.ordinal_position;
```

```sql
SELECT tc.table_name, kcu.column_name, ccu.table_name AS ref_table,
       ccu.column_name AS ref_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = :schema;
```

#### MySQL

```sql
SELECT table_name, ordinal_position, column_name, data_type,
       is_nullable, column_default, column_key
FROM information_schema.columns
WHERE table_schema = :db
ORDER BY table_name, ordinal_position;

SELECT table_name, column_name, referenced_table_name, referenced_column_name
FROM information_schema.key_column_usage
WHERE referenced_table_name IS NOT NULL
  AND table_schema = :db;
```

#### DuckDB

Las mismas consultas de `information_schema.columns` e
`information_schema.key_column_usage` que en Postgres; DuckDB soporta ambas.
Para archivos attached:
```sql
SELECT table_name FROM duckdb_tables() ORDER BY table_name;
```

### 3. Asignar un rol a cada columna (PK, FK, dim, measure, time, libre)

Después de extraer las listas de columnas, clasificar cada una por nombre y
tipo:

| Rol | Heurística |
|---|---|
| **PK** | `is_pk = 1` (SQLite) o columna única de una restricción `PRIMARY KEY` |
| **FK** | aparece en `key_column_usage` con un `referenced_table_name` no nulo |
| **dim (categórica)** | string / enum de baja cardinalidad / small-int, pocos valores distintos |
| **measure (numérica)** | tipo numérico (int / float / decimal), tiene sentido sumar/promediar |
| **time** | tipo `datetime` / `date` / `timestamp`, o nombre `*_at` / `*_date` / `*_ts` |
| **libre** | todo lo demás |

Hacer esto para cada tabla. La asignación de roles es lo que hace útil al
diccionario de datos (después podés filtrar "mostrame solo las medidas").

### 4. Identificar el grano por tabla

Para cada tabla, escribir una línea: "**Tabla X** — una fila por <entidad>".
Usar la PK y los nombres de columna para inferir:

- `fact_orders` — una fila por pedido
- `dim_users` — una fila por usuario
- `sessions` — una fila por sesión (no por usuario)
- `events` — una fila por evento

Si el grano es ambiguo (hace falta PK compuesta, no hay PK declarada),
**marcarlo** y preguntarle al usuario.

### 5. Mapear relaciones (explícitas + inferidas)

- **Explícitas** — las FKs encontradas en el paso 2 van al mapa de
  relaciones directamente.
- **Inferidas** — matching por nombre de columna (`user_id` en `orders` ↔
  `id` en `users`; `created_at` no es FK, saltearlo). Marcar las aristas
  inferidas con `(inferida)` en la salida; pedir confirmación del usuario
  antes de apoyarse en ellas en consultas.

Si dos tablas parecen joinearse a través de dos columnas distintas (p. ej.
`orders.billed_user_id` y `orders.shipped_user_id` podrían joinear ambas con
`users.id`), listar ambas posibilidades y preguntar cuál es la correcta.

### 6. Encontrar join paths (cuando se pregunte "¿cómo joineo X con Y?")

Construir un grafo dirigido desde el paso 5 (tabla → tabla vía la dirección de
la FK o su reverso). Para una consulta del usuario `(X, Y)`:

- Si hay FK directa → emitir un único JOIN.
- Si no, BFS al camino más corto. Emitir la cadena de JOINs multi-hop.
- Si no hay camino → emitir "no se encontró camino dentro del alcance del
  esquema; revisá `:other_schema`" o "no se encontró camino; la relación
  podría ser inferida o no existir".

Limitar el BFS a profundidad 3 para evitar productos cartesianos sorpresa.

### 7. Entregar

Guardar tres artefactos en `./schema/<nombre_db>-<YYYY-MM-DD>/`:

- `data-dictionary.md` — matriz tabla × columna con la columna de rol. Ordenar
  por nombre de tabla y luego posición ordinal. Incluir estimación de cantidad
  de filas desde `pg_stat_user_tables` / `information_schema.tables` cuando
  esté disponible.
- `join-paths.md` — una sección por `(X, Y)` que el usuario haya preguntado,
  más los 5 pares más probables inferidos por frecuencia de FK
  (orders ↔ users, orders ↔ products, etc.).
- `schema.mmd` — bloque Mermaid `erDiagram`. Convertir los tipos a un conjunto
  chico (`string`, `number`, `date`, `boolean`, `json`).

Incluir siempre la consulta de metadatos que se ejecutó al pie de cada
artefacto, para que el usuario pueda re-correrla o auditarla.

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "Solo `DESCRIBE` la tabla que necesito." | `DESCRIBE` solo muestra las columnas de UNA tabla. Sin el grafo de FK no podés joinear con confianza a una segunda tabla. |
| "Salto el diccionario, solo respondo la pregunta." | La próxima consulta va a necesitar el mismo contexto. Guardarlo una vez. |
| "Confío en la relación inferida." | Inferida ≠ enforced. Marcar como `(inferida)` y confirmar antes de que la consulta salga. |
| "No necesito los enunciados de grano — es obvio qué es cada tabla." | La ambigüedad de grano es una de las 3 principales fuentes de corrupción silenciosa del conteo de filas en joins. Siempre escribir el grano. |
| "Escaneo filas de muestra para entender el esquema." | El catálogo de metadatos es metadatos por algo. Escanear filas es 100× más data que la lista de columnas. |
| "Solo registro nombres de tablas y tipos, lo demás es overkill." | Los roles (PK / FK / dim / measure / time) son lo que hace utilizable al diccionario. Sin ellos es solo un volcado de columnas. |
| "Las foreign keys siempre están declaradas." | Solo en esquemas mantenidos con FKs en su lugar. Muchas DB reales carecen de enforcement de FK — el paso inferido es esencial. |
| "Embeco el ERD en el markdown de respuesta." | Guardarlo también a disco — el usuario (y el vos futuro) lo va a querer como referencia. |

## Señales de alerta

- Una tabla sin PK declarada y sin columna `id`/`uuid` obvia.
- Dos tablas con FKs que apuntan a la misma columna referenciada pero con
  **diferente** semántica (p. ej., `billed_user_id` vs `shipped_user_id`).
- Una tabla "fact" sin columna de tiempo (no se puede agregar en el tiempo).
- Una tabla "dim" cuya PK es un string (joins lentos, riesgos de encoding).
- Dos tablas con el **mismo** nombre en distintos schemas.
- MySQL donde `information_schema.key_column_usage` no devuelve filas — el
  esquema puede tener FKs no declaradas (solo inferidas).
- DuckDB donde el esquema está **attached** (no es `:memory:`) — los nombres
  de columna vuelven como `dbname.table_name.column_name`; quitar el
  prefijo antes de joinear entre bases.
- Un esquema sin FKs declaradas en lo que parece un warehouse normalizado —
  confirmar con el usuario si está normalizado o simplemente sin declarar.

## Verificación

- [ ] El motor y la versión fueron enunciados al inicio del trabajo.
- [ ] Los metadatos se obtuvieron desde `information_schema` (o equivalente);
  no se escanearon filas de muestra.
- [ ] Cada tabla tiene un enunciado de grano de una línea.
- [ ] Cada columna tiene un rol (PK / FK / dim / measure / time / libre);
  no hay columnas sin clasificar.
- [ ] Todas las FKs explícitas están en el mapa de relaciones; las aristas
  inferidas están marcadas con `(inferida)`.
- [ ] El diccionario de datos tiene estimaciones de cantidad de filas cuando
  el motor las soporta.
- [ ] El archivo ERD (`schema.mmd`) es Mermaid válido (renderiza sin error
  al pegarlo en un editor Mermaid live).
- [ ] Al menos un join path `(X, Y)` se probó con el algoritmo BFS; se
  emitió el camino más corto, no solo el primero encontrado.
- [ ] Los tres artefactos se guardaron en `./schema/<db>-<fecha>/`.
- [ ] El SQL de metadatos usado está incluido al pie de cada artefacto para
  auditoría y replay.
