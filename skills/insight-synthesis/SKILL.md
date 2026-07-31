---
name: insight-synthesis
description: Convierte hallazgos analíticos (estadísticas, gráficos, salidas de modelos) en insights priorizados y accionables usando el patrón Y Qué / Por Qué / Ahora Qué. Úsese después de que reporting-analyst produjo gráficos y un reporte escrito, cuando los hallazgos deban convertirse en decisiones. Se usa junto a reporting-analyst al final de cualquier análisis.
---

# Insight Synthesis

La última milla de cualquier análisis. Un gráfico + un reporte no es todavía
un insight — es evidencia cruda. Esta skill convierte la evidencia en el
conjunto priorizado y cuantificado de insights sobre los que un stakeholder
puede actuar.

## Descripción general

La mayoría de los flujos de analytics se detienen en "el gráfico de barras
muestra X". Eso es un hallazgo, no un insight. Esta skill impone tres
transformaciones a cada hallazgo:

1. **Y Qué** — por qué la magnitud le importa al negocio. Qué cambia si
   actuamos, qué cambia si no.
2. **Por Qué** — cuál es la explicación más probable, dado lo que está en
   los datos. (No especulación — lo que los datos mismos soportan.)
3. **Ahora Qué** — una acción específica con un verbo con dueño
   ("reducir", "subir", "investigar", "poner un guardrail", "matar feature").

La salida es un brief de 1 página con 3–5 insights, rankeados, cada uno con
impacto de negocio cuantificado y un puntaje explícito de confianza.

## Cuándo usar

- Existe un entregable de reporting-analyst (gráficos + reporte) y los
  stakeholders están preguntando "¿y qué?" / "¿qué significa esto para
  nosotros?".
- Hay múltiples hallazgos que hay que priorizar en un único "qué hacer esta
  semana".
- Un equipo va a actuar sobre el análisis pero necesita ayuda para
  secuenciarlo.
- El análisis se le está pasando a una audiencia no técnica.

No **usar** cuando:

- El gráfico en sí mismo es el entregable (saltar la síntesis — entregar
  solo el gráfico).
- No hay acciones posibles (investigación pura / "¿qué tienen los datos?")
  — el valor de la síntesis es la selección de acciones.
- El usuario solo quiere un resumen de una línea de un número — sintetizar
  inline.

## Flujo de trabajo

### 1. Enumerar cada hallazgo estadísticamente significativo

Listar cada hallazgo como **enunciado factual** (sin interpretar todavía):

- "La tasa de churn en la cohorte 2024-Q3 es 18.2%."
- "El ticket promedio es 24% mayor para usuarios adquiridos vía la campaña
  de septiembre."
- "La conversión en el paso 2 del funnel cayó 11 puntos porcentuales
  semana a semana."

Escribir 5–15 enunciados así. No filtrar todavía.

### 2. Aplicar Y Qué → Por Qué → Ahora Qué a cada hallazgo

Para cada enunciado, escribir tres líneas cortas:

```
Y Qué:    Churn al 18% significa que perdemos ~X clientes/trimestre al ritmo
          actual de crecimiento; tenemos un runway de 2 trimestres antes de
          que el target de adquisición de nuevos clientes se vuelva
          inalcanzable.
Por Qué:  La caída coincide con el [cambio específico] del [fecha], no con
          patrones estacionales de los 8 trimestres previos.
Ahora Qué: Lanzar un experimento de retención dirigido a la cohorte 2024-Q3
          antes de [fecha]; congelar trabajo de features nuevas sobre la
          superficie afectada por 2 semanas.
```

Si no podés escribir un Y Qué cuantificado, degradar el hallazgo a
"observación" y moverlo al apéndice.

### 3. Puntuar cada insight: impacto × confianza × accionabilidad

| Dimensión | 1 (bajo) | 2 (medio) | 3 (alto) |
|---|---|---|---|
| **Impacto** (financiero, cliente, operacional) | <5% de la métrica | 5–20% | >20% |
| **Confianza** (estadística + metodológica) | muestra única, sin baseline | repetido, baseline parcial | replicado, controlado |
| **Accionabilidad** | "hace falta más análisis" | existe acción pero dueño incierto | un equipo, una decisión |

Conservar los insights que puntúan ≥6/9 en el top-5. Poner el resto en el
apéndice.

### 4. Agrupar, resolver conflictos, señalar

- Agrupar insights relacionados (p. ej., múltiples hallazgos sobre el mismo
  paso del funnel).
- Si dos hallazgos se contradicen, **nombrar la tensión** explícitamente y
  enunciar qué datos adicionales la resolverían. No esconder conflictos.
- Señalar los límites del análisis en un párrafo: tamaño de muestra,
  ventana temporal, caveats de definición.

### 5. Entregar el brief de insight

Markdown de una página, secciones:

1. **TL;DR** — 3 bullets, los 3 Y Qué más importantes.
2. **Top 5 insights** — cada uno con: hallazgo, Y Qué, Por Qué, Ahora Qué,
   estimación de impacto, confianza (1–3).
3. **Qué necesitaríamos saber a continuación** — un párrafo sobre las
   preguntas abiertas.
4. **Apéndice** — observaciones degradadas.

Si el usuario pidió un write-up más largo, expandir cada insight a un
párrafo con los números subyacentes inline.

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "Simplemente resumimos el gráfico y lo llamamos insight." | Un resumen es re-enunciar la evidencia; un insight requiere Y Qué / Por Qué / Ahora Qué. |
| "No conocemos el impacto financiero, salteamos el número." | Usar una estimación de orden de magnitud ($10k vs $1M es accionable; la precisión importa menos que el orden). |
| "Los stakeholders van a hacer su propia priorización." | Pre-rankear el top 5. Si dos insights son igualmente importantes, decirlo y explicar el desempate. |
| "Más análisis mejoraría la confianza, entonces difiero la síntesis." | Entregar lo que hay con confianza explícitamente puntuada; la perfección es enemiga de la acción. |
| "Cada hallazgo del gráfico merece un insight." | No — algunos son observaciones. Ponerlos en el apéndice, no en el top 5. |
| "Un solo insight grande alcanza." | Un único Y Qué rara vez es cierto; los datos suelen soportar 3–5 insights distintos. |

## Señales de alerta

- Un brief de insight con **ningún impacto cuantificado** en ninguna parte.
- Un insight con Y Qué pero **sin Ahora Qué** (es una observación, no un
  insight).
- Un insight basado en una muestra de <30 eventos o sin baseline.
- Una lista "rankeada" donde cada item puntúa igual — el ranking es falso.
- Insights que se contradicen sin nombrar la contradicción.
- Enterrar las malas noticias en el apéndice mientras se arranca con
  sesgo de confirmación.
- Faltar insights específicos por stakeholder (p. ej., un brief orientado a
  finanzas sin línea de revenue, un brief de ops sin línea de SLA).

## Verificación

- [ ] Cada hallazgo listado en el paso 1 está en el top 5 o en el
  apéndice (sin drops silenciosos).
- [ ] Cada insight del top 5 tiene un Y Qué cuantificado (aunque sea
  orden de magnitud).
- [ ] Cada insight tiene un Ahora Qué explícito con un verbo de acción.
- [ ] Cada insight tiene un puntaje impacto × confianza × accionabilidad y
  la aritmética cierra (cada puntaje 1–3, suma 3–9).
- [ ] El top 5 está ordenado por el puntaje; los empates se anotan
  explícitamente con un desempate.
- [ ] Al menos un párrafo nombra los límites (tamaño de muestra, ventana
  temporal, caveats).
- [ ] Si dos hallazgos se contradicen, la contradicción y el plan de
  resolución están escritos.
- [ ] El TL;DR tiene 3 bullets y matchea con el top 3 de la lista
  rankeada.
- [ ] El entregable entra en una página (la versión extendida es opcional,
  pero el brief de una página siempre existe).
