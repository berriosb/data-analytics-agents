---
name: query-validation
description: Revisa una consulta SQL por correctitud, anti-patrones y comportamiento específico del motor antes de que salga a producción o alimente un dashboard. Úsese después de que sql-query-helper produzca una consulta, o cuando una consulta devuelva resultados sorprendentes, corra lento, o esté siendo promovida de exploración a producción. Se usa junto a sql-query-helper.
---

# Query Validation

Una consulta que "corrió y devolvió números" no es todavía una consulta segura
para sacar a producción. Esta skill es el pase de revisión entre "escribe SQL"
y "usa SQL en un dashboard / reporte / sistema de producción". Atrapa la clase
de bugs que se le escapan a las revisiones a nivel de idioma: anti-patrones,
olores de performance, foot-guns específicos del motor y errores de lógica
que sobreviven a los chequeos de sintaxis.

Esta skill **complementa** a `sql-query-helper` (que provee idiomas según
motor para escribir consultas). Usá `sql-query-helper` para escribir, y
después esta skill para revisar.

## Descripción general

Una revisión de consulta tiene cuatro pases:

1. **Lint** — violaciones de sintaxis y estilo (lo barato).
2. **Chequeo de anti-patrones** — foot-guns conocidos por motor (el pase de
   alto rendimiento).
3. **Revisión de cardinalidad y plan** — ¿escanea cuando podría hacer seek?
4. **Recorrido de lógica** — ¿el resultado coincide con la definición de
   negocio?

Cada pase produce un hallazgo estructurado (severidad, ubicación, fix). La
salida es una plantilla de revisión de consulta sobre la que el escritor
actúa, no un bloqueo al envío.

## Cuándo usar

- Una consulta está por alimentar un dashboard, reporte programado o modelo
  downstream.
- Una consulta devuelve números sorprendentes pero el motor "la ejecutó sin
  error".
- Una consulta que funcionó en dev se vuelve lentísima en prod.
- Se está portando una consulta entre motores.
- Un usuario dice "este número se ve mal" y la consulta es la principal
  sospechosa.

No **usar** cuando:

- La consulta es exploración one-shot (`SELECT COUNT(*)` para orientarse).
- La consulta es trivial (<5 líneas, una sola tabla, sin joins).
- El usuario dice explícitamente "no revises, simplemente córrelo".

## Flujo de trabajo

### 1. Enunciar los inputs

Antes de revisar, escribir:

- El texto completo de la consulta (un bloque).
- El motor destino y la versión.
- Las tablas tocadas (con cantidades de filas aproximadas si se conocen).
- El resultado de negocio esperado: "esto debería dar igual a X para el mismo
  rango de fechas".
- Si hay un `EXPLAIN` / perfil de consulta disponible.

Sin esto, no podés juzgar si el resultado es correcto.

### 2. Pase 1 — Lint

Correr un pase programático donde esté disponible, sino escanear a ojo:

- **sqlglot** (`sqlglot.parse(sql).errors()` o `sqlfluff lint` para chequeos
  estilo dbt) — atrapa paréntesis desbalanceados, comas al final, palabras
  reservadas como alias.
- **Estilo** — alias de tabla (`t1`, `o` están bien), capitalización
  consistente, sin comentarios en cada línea, punto y coma final donde el
  motor lo pide.

Los errores duros bloquean la revisión (volver al escritor). Los issues de
estilo van a la salida de la revisión como severidad LOW.

### 3. Pase 2 — Chequeo de anti-patrones

Escanear la consulta contra la lista siguiente. Cada item encontrado →
fila de hallazgo:

| # | Anti-patrón | Por qué muerde | Motores |
|---|---|---|---|
| 1 | `SELECT *` en consulta no trivial | el orden de columnas rompe a los consumidores; trae columnas BLOB | todos |
| 2 | `SELECT DISTINCT` para "deduplicar" | colapsa filas, no elige la última por clave | todos |
| 3 | CTE sin límite (subquery sin `WHERE` o `LIMIT` en tablas grandes) | escanea toda la tabla aunque el downstream use 10 filas | todos |
| 4 | `WHERE col LIKE '%foo%'` | wildcard al inicio → full table scan | todos |
| 5 | Función sobre columna indexada (`WHERE DATE(ts) = …`) | mata el índice | todos |
| 6 | Coerción de tipo implícita (`WHERE numeric_col = '123'`) | evita el índice, puede matchear filas extra | todos |
| 7 | `NOT IN (subquery)` | NULL en el subquery → resultado vacío silencioso | todos |
| 8 | Unión de columnas nulables sin `COALESCE` | los NULL se propagan inesperadamente | todos |
| 9 | Igualdad / acumulación de punto flotante | pérdida de precisión | todos |
| 10 | `ORDER BY` sin `LIMIT` sobre tabla de 100M filas | manda todo el resultado a un cliente | todos |
| 11 | `OFFSET 100000` para paginar | escanea + descarta 100k filas | todos |
| 12 | `INSERT … SELECT` sin lista explícita de columnas | depende del orden; rompe ante cambio de esquema | todos |
| 13 | Matemática de fechas vía concat de strings (`WHERE ts = '2024-' \|\| month`) | rompe con locale, sin índice | todos |
| 14 | `HAVING` sin `GROUP BY` (confiando en agregación implícita) | portabilidad | todos |
| 15 | Reutilizar nombre de columna como alias (`SELECT col1 AS col1`) | algunos motores resuelven alias-tabla.columnas que no existen | Postgres |

### 4. Pase 3 — Cardinalidad y revisión de plan

Si el motor tiene `EXPLAIN` (Postgres / MySQL / SQLite ≥ 3.16) o perfil de
consulta (DuckDB `EXPLAIN ANALYZE`, Snowflake / BigQuery query history):

- **Full table scan sobre una tabla >1M filas** que tiene un índice
  relevante → marcar.
- **Hash join cuando nested-loop con índice serviría** a bajo conteo de
  filas → marcar.
- **CTE materializado re-evaluado por referencia** (default en Postgres <12)
  → marcar si el CTE es grande.
- **Estimación de cardinalidad desviada por >10×** de los valores reales
  (DuckDB / Snowflake) → marcar el join que se desvió.

Si no hay plan disponible, estimar cardinalidad manualmente:

- Para cada join: cuántas filas a izquierda × derecha × selectividad del
  predicado. Si no podés acotarlo, la consulta no es segura a escala.

### 5. Pase 4 — Recorrido de lógica

Recorrer la consulta con el resultado esperado a mano:

- Para cada fila que la consulta devolverá, predecir los valores columna a
  columna.
- Para agregaciones, predecir el conteo y la suma con una muestra mental de
  una fila.
- Si hay un filtro de fecha, aplicarlo al predicado a mano sobre una fecha
  de ejemplo.

Si el recorrido mental no coincide con el resultado real devuelto (en dev o
staging), la consulta está mal; no la saques.

### 6. Emitir la revisión

Un único doc markdown, secciones:

```
## Revisión de consulta — <nombre o id corto>
Motor:  <motor>
Fecha:  <YYYY-MM-DD>
Revisor: <agente o humano>

### Veredicto
APROBADA | APROBADA CON NOTAS | BLOQUEADA

### Hallazgos
| # | Severidad | Pase | Ubicación | Hallazgo | Fix sugerido |

### Notas de plan
<lo destacado del EXPLAIN, o "no revisada — no hay plan disponible">

### Recorrido de lógica
<un párrafo>

### Aprobación requerida de
<quién debe aprobar antes de salir>
```

Escala de severidad: **BLOQUEANTE** (resultado incorrecto o costo sin
límite), **ALTA** (anti-patrón que va a causar incidentes a escala), **MEDIA**
(anti-patrón que afecta performance / legibilidad), **BAJA** (estilo).

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "La consulta devolvió el número correcto en mi test, la saco." | Los tests rara vez cubren escala, NULLs o cambios de esquema futuros. La revisión es un seguro barato. |
| "La probé en la tabla chica de dev, la performance está bien." | Los anti-patrones que están bien a 1k filas son catastróficos a 100M filas. El pase 3 es la barrera. |
| "DISTINCT lo limpió." | `DISTINCT` es casi siempre la herramienta equivocada para dedup. Usá `ROW_NUMBER` por clave (ver sql-query-helper). |
| "`SELECT *` está bien, es interno." | Las herramientas internas se vuelven externas. Listá las columnas ahora. |
| "EXPLAIN es overkill, la consulta solo tiene una tabla." | Las consultas de una sola tabla igual se benefician del chequeo de anti-patrones (#4, #5, #10). |
| "Agrego la lista de columnas después." | "Después" nunca llega antes de producción. Agregar 30 segundos de edición ahora ahorra un incidente después. |
| "Funcionó en MySQL, va a funcionar en Postgres." | El manejo de NULL, las funciones de fecha y la coerción difieren. La columna de motor en la revisión fuerza al escritor a chequear. |

## Señales de alerta

- Una revisión que encuentra **cero hallazgos MEDIA/ALTA en una consulta
  de 100+ líneas** — el revisor no miró con suficiente detalle.
- Una revisión que **no tiene Pase 4 (recorrido de lógica)** — ahí se
  esconden la mayoría de los bugs reales de correctitud.
- Aprobar una consulta que **toca una tabla >1M filas sin un EXPLAIN** o
  estimación de cardinalidad manual.
- Aprobar una consulta que devuelve un número que el revisor no puede
  predecir solo desde el SQL (significa que el SQL está haciendo algo que
  el revisor no ve).
- "Aprobada con notas" donde las notas incluyen un **BLOQUEANTE** — eso es
  BLOQUEADA, no aprobada.
- La misma consulta aprobada dos veces seguidas porque el revisor no la
  re-recorrió después de un cambio de esquema.

## Verificación

- [ ] El motor y la versión están enunciados al inicio.
- [ ] Los inputs (texto de consulta, motor destino, tablas, resultado
  esperado) están registrados.
- [ ] El Pase 1 corrió (sin errores duros) o se salteó con razón.
- [ ] El Pase 2 cubrió los 15 anti-patrones; cada hit está en la tabla de
  hallazgos.
- [ ] El Pase 3 produjo un resumen de EXPLAIN o una estimación de
  cardinalidad escrita.
- [ ] El Pase 4 produjo un párrafo de recorrido de lógica que predice los
  valores de una fila.
- [ ] La tabla de hallazgos tiene severidad, número de pase, ubicación,
  hallazgo, fix.
- [ ] El veredicto (APROBADA / APROBADA CON NOTAS / BLOQUEADA) está
  nombrado y coincide con la mayor severidad de los hallazgos.
- [ ] La aprobación está nombrada (qué equipo / persona debe aprobar antes
  de salir).
