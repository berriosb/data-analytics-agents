---
name: using-data-analytics-agents
description: Clasifica una tarea de datos y enruta al agente especialista correcto (data-explorer, sql-analyst, reporting-analyst). Úsese al iniciar una sesión, cuando el pedido del usuario sea ambiguo, o cuando pregunte qué agente usar.
---

# Using Data Analytics Agents

La skill de triaje. Léase una vez por tarea, clasifíquese, enrutese, parar.

## Descripción general

Existen tres agentes especialistas en este toolkit. Cada uno tiene un alcance
estrecho. Cargar el agente equivocado desperdicia contexto y produce respuestas
superficiales. Esta skill existe para hacer la decisión de enrutamiento
explícita y revisable.

## Cuándo usar

- El pedido del usuario es ambiguo o podría encajar con varios agentes.
- El usuario pregunta explícitamente "¿qué agente debería usar?".
- El usuario pega un archivo (CSV, volcado SQL, captura) sin instrucción.
- Acaba de iniciar una sesión nueva y aún no clasificó la tarea.

No **usar** cuando:

- El usuario nombra un agente directamente ("data-explorer, hacé X").
- El pedido tiene un solo verbo claro y un objetivo claro
  ("consultá la tabla customers").
- El pedido no es una tarea de datos.

## Flujo de trabajo

### 1. Leer el pedido

Extraer el/los verbo(s) y el objetivo. Ejemplo:

> "Resumí las ventas del último trimestre y armá un gráfico para el directorio"

→ Verbos: `resumí`, `armá`. Objetivo: `ventas` (último trimestre), `gráfico`.
→ Abarca **dos** agentes: `data-explorer` (resumir) + `reporting-analyst`
  (gráfico).

### 2. Cotejar contra la tabla de enrutamiento

| Verbos / señales | Objetivo | Agente | Skill a cargar |
|---|---|---|---|
| perfilar, limpiar, preprocesar, dtype, faltantes, outliers, explorar, entender | CSV / Parquet / Excel (sin esquema) | `data-explorer` | `csv-profiler`, luego `pandas-cleaning` |
| "qué columnas / filas tiene", "hay relación entre X e Y" | CSV (sin SQL disponible) | `data-explorer` | `csv-profiler` |
| consultar, select, join, agregar, agrupar por, filtrar where, esquema, índices, explain | base SQL, archivo .sql, SQLite | `sql-analyst` | `schema-mapper`, luego `sql-query-helper`, luego `query-validation` |
| gráfico, plot, visualizar, dashboard, resumen ejecutivo, reporte, PDF, HTML | dataframe o resultado SQL | `reporting-analyst` | `viz-patterns`, luego `insight-synthesis` |
| "no sé qué tiene este archivo", "primer vistazo" | cualquier archivo de datos | `data-explorer` | `csv-profiler` primero |
| verbos ambiguos como "resumir", "mirá", "revisá" | depende del objetivo — preguntar | triaje | ninguno (solo preguntar) |

### 3. Enunciar la clasificación

Una línea, citando la señal:

> Clasificado como **perfil/EDA** (verbo: "explorar"; objetivo: CSV). Se
> recomienda `data-explorer` con la skill `csv-profiler`.

### 4. Confirmar con el usuario

Hacer una sola pregunta:

> ¿Procedo con `data-explorer`? (sí / también cargar `pandas-cleaning` /
> elegir otro)

**No** empezar a cargar archivos ni correr herramientas hasta que el usuario
confirme.

### 5. Parar

Pasarle el control al agente elegido. El especialista se hace cargo del trabajo
desde acá.

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "El pedido es obvio — simplemente ejecutalo." | Incluso los pedidos obvios se benefician de un traspaso explícito; reduce errores. |
| "Cargo `csv-profiler` por las dudas." | Cargar una skill sin un plan claro diluye el contexto. |
| "Dos agentes en paralelo será más rápido." | La ejecución secuencial mantiene el alcance de cada agente estrecho. La ejecución paralela concatena ruido. |
| "El usuario quiere velocidad, salto la pregunta." | Una pregunta cuesta ~5 segundos; el churn por agente equivocado cuesta minutos. |

## Señales de alerta

- El pedido menciona "reporte" y "exploración de datos crudos" — son dos
  agentes, no uno. Recomendar una secuencia y preguntar cuál correr primero.
- El usuario subió un archivo `.sql` y pidió un "resumen" — eso es
  `sql-analyst`, no `reporting-analyst` (todavía no hay gráfico).
- El usuario dijo "usá la skill que te parezca" sin archivo adjunto —
  pedir el archivo o la pregunta, no adivinar.

## Verificación

- [ ] La clasificación cita un verbo + objetivo del pedido.
- [ ] Se recomienda un solo agente, o se propone una secuencia para
  pedidos multi-dominio.
- [ ] Se preguntó al usuario antes de cargar cualquier herramienta o skill.
- [ ] No se abrió ningún archivo ni se ejecutó ninguna consulta por el agente
  de triaje mismo.
