---
name: viz-patterns
description: Elige el tipo de gráfico de Plotly correcto según los tipos de variables y la pregunta; provee recetas de Plotly para tendencias, distribuciones, categorías, relaciones y partes-de-un-todo. Úsese cuando el usuario quiera un gráfico y la pregunta a responder sea inequívoca.
---

# Viz Patterns

Plotly primero. Un gráfico = un mensaje. Elegir el tipo por variables y
pregunta, no por hábito.

## Descripción general

Una tabla de decisión que mapea (tipos de variables × pregunta) a un tipo de
gráfico, más recetas de Plotly listas para pegar en los casos comunes. Usar
esta skill **después** de que los datos estén limpios y la pregunta clara.

## Cuándo usar

- Los datos están limpios y la pregunta es clara.
- El usuario nombra un tipo de gráfico o hace una pregunta que mapea de
  forma directa.
- La audiencia está definida (directorio / analista / reporte).

No **usar** cuando:

- Los datos son crudos → correr `csv-profiler` primero.
- La pregunta es ambigua → preguntar antes de graficar.
- El usuario quiere un dashboard custom (layout multi-gráfico) → igual
  elegir tipos de gráfico por panel, pero ensamblarlos como subplots.

## Variable × pregunta → tipo de gráfico

| Pregunta | Eje X | Eje Y | Color / facet | Gráfico | Llamada Plotly |
|---|---|---|---|---|---|
| ¿Cómo cambia Y a lo largo del tiempo? | datetime | numérica | categórica opcional | line | `px.line` |
| Comparar categorías en un único valor numérico | categórica | numérica | — | bar (vertical) | `px.bar` |
| Rankear categorías por un único valor numérico | categórica | numérica | — | bar (horizontal, ordenada) | `px.bar(orientation="h")` |
| Distribución de una variable numérica | — | numérica (cuenta) | — | histogram | `px.histogram` |
| Distribución de una numérica entre categorías | categórica | numérica | — | box / violin | `px.box` / `px.violin` |
| Relación entre dos numéricas | numérica | numérica | categórica opcional | scatter | `px.scatter` |
| Partes de un todo (≤5 categorías) | categórica | numérica | — | pie | `px.pie` |
| Matriz de correlación entre varias numéricas | — | — | — | heatmap | `px.imshow` |
| Conteos por dos categóricas | categórica | categórica | — | heatmap | `px.density_heatmap` |
| Cambio de distribución entre categorías | categórica | numérica | segunda categórica | ridge / strip / box | `px.strip` / `px.box` |
| Tendencias entre muchas series | datetime | numérica | categórica | multi-line (small multiples si >5) | `px.line(facet_col=…)` |

## Reglas de decisión

1. **Tiempo en x** → `line`. Siempre. Incluso con "buckets" categóricos de
   fechas.
2. **X categórica, Y numérica** → `bar`. Horizontal si los labels son largos.
3. **Una distribución numérica** → `histogram` si n es grande (>200), si no
   `box`.
4. **Dos numéricas** → `scatter`. Si es denso (n>2k), cambiar a
   `density_heatmap`.
5. **Partes de un todo** → `pie` **solo** si ≤5 categorías y los totales son
   significativos. Si no, `bar` ordenada.
6. **Matriz de correlación** → `heatmap` con colormap secuencial (sin
   divergente).
7. **Muchas series (>5)** → facet (small multiples), no overlay.
8. **Hay outliers** → cap al percentil 99 *con footnote*, no descartar en
   silencio.

## Recetas

### Bar — top categorías

```python
import plotly.express as px

agg = df.groupby(<col_categorica>, as_index=False)[<col_numerica>].sum()
agg = agg.sort_values(<col_numerica>, ascending=False).head(10)

fig = px.bar(
    agg,
    x=<col_categorica>,
    y=<col_numerica>,
    title=f"<col_numerica> por <col_categorica> — top 10",
    labels={<col_categorica>: "<Etiqueta>", <col_numerica>: "<Etiqueta> (<unidad>)"},
)
fig.update_layout(showlegend=False)
```

### Line — serie única con media móvil

```python
import plotly.express as px

df_sorted = df.sort_values(<col_fecha>)
df_sorted["rolling"] = df_sorted[<col_numerica>].rolling(window=7).mean()

fig = px.line(
    df_sorted,
    x=<col_fecha>,
    y=[<col_numerica>, "rolling"],
    title="<col_numerica> diaria con media móvil de 7 días",
    labels={<col_fecha>: "Fecha", "value": "<Etiqueta> (<unidad>)"},
)
```

### Scatter — relación con línea de regresión

```python
import plotly.express as px

fig = px.scatter(
    df,
    x=<numerica_x>,
    y=<numerica_y>,
    color=<col_categorica> or None,
    trendline="ols",  # requiere statsmodels
    title="<numerica_y> vs <numerica_x>",
    labels={<numerica_x>: "<Etiqueta> (<unidad>)", <numerica_y>: "<Etiqueta> (<unidad>)"},
)
```

### Histogram — distribución con umbral

```python
import plotly.express as px

fig = px.histogram(
    df,
    x=<col_numerica>,
    nbins=30,
    title=f"Distribución de <col_numerica> (n={len(df):,})",
)
```

### Box — distribución entre categorías

```python
import plotly.express as px

fig = px.box(
    df,
    x=<col_categorica>,
    y=<col_numerica>,
    title=f"<col_numerica> por <col_categorica>",
)
```

### Heatmap — matriz de correlación

```python
import plotly.express as px

corr = df[[<cols_numericas>]].corr()
fig = px.imshow(
    corr,
    text_auto=".2f",
    aspect="auto",
    color_continuous_scale="RdBu_r",
    zmin=-1, zmax=1,
    title="Matriz de correlación",
)
```

### Line facetado — muchas series

```python
import plotly.express as px

fig = px.line(
    df,
    x=<col_fecha>,
    y=<col_numerica>,
    facet_col=<col_categorica>,
    facet_col_wrap=4,
    title="<col_numerica> por <col_categorica>",
)
fig.update_yaxes(matches=None)
```

## Configuración de salida

```python
fig.update_layout(
    template="simple_white",
    title_font_size=16,
    font=dict(size=12),
    margin=dict(l=60, r=20, t=60, b=40),
)
```

Guardar:

```python
fig.write_html(out_html, include_plotlyjs="cdn")  # HTML liviano, ~3MB via CDN
fig.write_image(out_png, width=1200, height=700, scale=2)  # requiere `kaleido`
```

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "Los gráficos de torta están bien." | Solo cuando las partes son comparables y hay <5 categorías. |
| "Trunco el eje y para que se vea la diferencia." | Engaña al lector. Usar escala log o un panel normalizado. |
| "Voy a usar un gráfico de barras 3D." | El 3D codifica una dimensión extra a costa de claridad. Rechazar. |
| "Escondo outliers para que el gráfico se vea más limpio." | Cap y footnote, o anotar — nunca ocultar en silencio. |
| "Un bar con muchas categorías está bien." | Top-10 + bucket "otros"; si no, es ilegible. |

## Señales de alerta

- Gráfico `pie` con >5 categorías.
- Gráfico `line` con eje X categórico (no datetime).
- `bar` con X e Y ambas numéricas.
- `bar` apilado con >5 stacks — facet en su lugar.
- `scatter` con >5k puntos sin reducción de marcadores → cambiar a
  `density_heatmap`.
- Título que nombra una variable en vez de un hallazgo.

## Verificación

- [ ] El tipo de gráfico coincide con los tipos de variables y la pregunta.
- [ ] El título enuncia la conclusión (no los nombres de variables).
- [ ] Las etiquetas de los ejes incluyen unidades cuando corresponde.
- [ ] La leyenda está presente para >1 serie, oculta para 1 serie.
- [ ] El caption incluye fuente de datos + conteo de filas + manejo de
  outliers.
- [ ] Los archivos de salida existen (`.html` para interactivo, `.png`
  para estático).
