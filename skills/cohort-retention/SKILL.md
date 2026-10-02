---
name: cohort-retention
description: Análisis y visualización de retención por cohortes en datos tabulares y transaccionales (matriz triangular de cohortes, retención N-período, tasa de churn, métricas acumuladas y heatmap Plotly adaptativo). Úsese cuando el usuario pida análisis de cohortes, retención de clientes o usuarios, curvas de churn, o comportamiento longitudinal en el tiempo.
---

# Cohort Retention

Especializada en modelar el comportamiento longitudinal de usuarios o clientes
agrupados por momento de adquisición (cohorte). Transforma eventos transaccionales
o de actividad en matrices triangulares de retención y genera visualizaciones
claras y accionables.

## Descripción general

La métrica agregada en el tiempo (ej. "MAU crece 5%") oculta a menudo si el
crecimiento proviene de adquirir usuarios nuevos o de retener a los existentes.
Esta skill provee snippets probados para:

1. **Construir la matriz de retención**: agrupar por cohorte (mes, semana o día
   de primera actividad) y medir el porcentaje activo en periodos sucesivos
   ($t_0, t_1, \dots, t_n$).
2. **Calcular la curva de decaimiento (churn y retención media)**: identificar en
   qué periodo se aplana la curva (Product-Market Fit).
3. **Visualizar el heatmap triangular en Plotly**: matriz de calor con
   porcentajes formateados inline y escala adaptativa.
4. **Patrón SQL analítico multi-motor**: consulta lista para bases de datos
   relacionales y cloud warehouses.

## Cuándo usar

- Cuando el dataset contiene identificador de entidad (`user_id`, `customer_id`,
  `account_id`) y fechas de eventos/transacciones.
- Cuando el usuario pregunta:
  - "¿Cómo es la retención mes a mes de los clientes adquiridos este año?"
  - "¿Cuál es la tasa de churn por cohorte?"
  - "Mostrame una matriz de cohortes."
  - "¿Se está aplanando la curva de retención?"
- Como paso analítico en `data-explorer` o `reporting-analyst` tras limpiar el dataset.

No **usar** cuando:

- Los datos no tienen identificador único por entidad o dimensión temporal.
- El usuario solo pide series temporales agregadas (tendencia general) → usar
  `time-series-patterns`.
- No hay eventos repetidos (cada entidad aparece exactamente una sola vez).

## Snippets pre-aprobados (Pandas + Plotly)

### `build_cohort_matrix(df, user_col, date_col, freq="M")` — construir matriz triangular

```python
import pandas as pd
import numpy as np

def build_cohort_matrix(df, user_col, date_col, freq="M"):
    """Construye la matriz de tamaño de cohorte y porcentaje de retención.

    freq: 'M' (mensual), 'W' (semanal), 'D' (diaria).
    Devuelve dict con:
      - 'cohort_counts': DataFrame con recuento absoluto de usuarios.
      - 'cohort_retention': DataFrame con porcentaje relativo (100% en periodo 0).
      - 'cohort_sizes': Series con tamaño inicial de cada cohorte.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[user_col, date_col])

    if freq == "M":
        period_dt = df[date_col].dt.to_period("M")
    elif freq == "W":
        period_dt = df[date_col].dt.to_period("W")
    elif freq == "D":
        period_dt = df[date_col].dt.to_period("D")
    else:
        raise ValueError(f"Frecuencia no soportada: {freq}. Usar 'M', 'W' o 'D'.")

    df["order_period"] = period_dt
    df["cohort_group"] = df.groupby(user_col)["order_period"].transform("min")

    # Calcular índice de periodo (0, 1, 2, ...)
    if freq == "M":
        df["period_number"] = (
            (df["order_period"].dt.year - df["cohort_group"].dt.year) * 12
            + (df["order_period"].dt.month - df["cohort_group"].dt.month)
        )
    else:
        df["period_number"] = (df["order_period"] - df["cohort_group"]).apply(lambda x: x.n)

    # Agrupar cohortes
    grouped = df.groupby(["cohort_group", "period_number"])[user_col].nunique().reset_index()
    cohort_counts = grouped.pivot(index="cohort_group", columns="period_number", values=user_col)
    cohort_sizes = cohort_counts.iloc[:, 0]
    cohort_retention = cohort_counts.divide(cohort_sizes, axis=0) * 100.0

    # Convertir índices a string legible
    cohort_counts.index = cohort_counts.index.astype(str)
    cohort_retention.index = cohort_retention.index.astype(str)

    return {
        "cohort_counts": cohort_counts,
        "cohort_retention": cohort_retention,
        "cohort_sizes": cohort_sizes,
    }
```

### `calculate_retention_summary(cohort_retention)` — curva media y churn acumulado

```python
def calculate_retention_summary(cohort_retention):
    """Calcula la curva de retención promedio ponderada y churn periodo a periodo."""
    mean_retention = cohort_retention.mean(axis=0)
    median_retention = cohort_retention.median(axis=0)
    churn_rate = 100.0 - mean_retention

    # Churn marginal periodo a periodo
    marginal_churn = mean_retention.diff().abs()

    summary_df = pd.DataFrame({
        "mean_retention_pct": mean_retention,
        "median_retention_pct": median_retention,
        "cumulative_churn_pct": churn_rate,
        "marginal_drop_pct": marginal_churn,
    })
    return summary_df
```

### `plot_cohort_heatmap(cohort_retention, title="Matriz de Retención de Cohortes (%)", colormap="Blues")` — visualización Plotly

```python
import plotly.graph_objects as go

def plot_cohort_heatmap(cohort_retention, title="Matriz de Retención por Cohortes (%)", colormap="Blues"):
    """Genera heatmap triangular con anotaciones de porcentajes y escala clara."""
    z_values = cohort_retention.values
    x_labels = [f"Periodo {c}" for c in cohort_retention.columns]
    y_labels = list(cohort_retention.index)

    # Text annotations para cada celda
    annotations = []
    for i, row in enumerate(z_values):
        for j, val in enumerate(row):
            if not np.isnan(val):
                annotations.append(
                    dict(
                        x=x_labels[j],
                        y=y_labels[i],
                        text=f"{val:.1f}%",
                        showarrow=False,
                        font=dict(color="white" if val > 50 else "#222222", size=10),
                    )
                )

    fig = go.Figure(
        data=go.Heatmap(
            z=z_values,
            x=x_labels,
            y=y_labels,
            colorscale=colormap,
            zmin=0,
            zmax=100,
            hoverongaps=False,
            colorbar=dict(title="% Retención"),
        )
    )

    fig.update_layout(
        title=dict(text=title, x=0.5),
        xaxis=dict(title="Periodos transcurridos desde adquisición", side="top"),
        yaxis=dict(title="Cohorte de Adquisición", autorange="reversed"),
        annotations=annotations,
        margin=dict(l=80, r=40, t=100, b=40),
        height=max(400, len(y_labels) * 35 + 150),
    )
    return fig
```

## Patrón de consulta SQL analítico (Postgres / DuckDB / Snowflake / BigQuery)

```sql
WITH user_first_activity AS (
  -- 1. Determinar el periodo de cohorte (adquisición) de cada usuario
  SELECT
    user_id,
    DATE_TRUNC('month', MIN(event_date)) AS cohort_month
  FROM events
  GROUP BY user_id
),
user_activities AS (
  -- 2. Mapear cada actividad posterior al mes correspondiente
  SELECT
    e.user_id,
    DATE_TRUNC('month', e.event_date) AS activity_month
  FROM events e
  GROUP BY e.user_id, DATE_TRUNC('month', e.event_date)
),
cohort_sizes AS (
  -- 3. Contar tamaño base de cada cohorte en periodo 0
  SELECT
    cohort_month,
    COUNT(DISTINCT user_id) AS total_users
  FROM user_first_activity
  GROUP BY cohort_month
),
retention_counts AS (
  -- 4. Contar usuarios activos por cohorte y distancia en meses
  SELECT
    f.cohort_month,
    -- Diferencia en meses entre actividad y cohorte (sintaxis DuckDB/Postgres)
    (EXTRACT(year FROM a.activity_month) - EXTRACT(year FROM f.cohort_month)) * 12 +
    (EXTRACT(month FROM a.activity_month) - EXTRACT(month FROM f.cohort_month)) AS period_number,
    COUNT(DISTINCT a.user_id) AS active_users
  FROM user_first_activity f
  JOIN user_activities a ON f.user_id = a.user_id
  GROUP BY f.cohort_month, period_number
)
SELECT
  r.cohort_month,
  s.total_users AS cohort_size,
  r.period_number,
  r.active_users,
  ROUND(r.active_users * 100.0 / s.total_users, 2) AS retention_pct
FROM retention_counts r
JOIN cohort_sizes s ON r.cohort_month = s.cohort_month
ORDER BY r.cohort_month, r.period_number;
```

## Señales de alerta

- **Cohorte con retención > 100% en periodos posteriores**: Suele deberse a mala
  definición del evento de cohorte (ej. filtrar pedidos pagados en la actividad pero
  no en la cohorte).
- **Muestra muy pequeña en cohortes recientes**: En periodos incompletos
  (ej. cohorte del mes actual a mitad de mes), advertir que el periodo 0 está incompleto.
- **Efecto estacional vs decaimiento real**: Contrastar siempre si una caída en $t_2$
  afecta a todas las cohortes simultáneamente (problema de estacionalidad o bug de producto)
  o solo a una cohorte específica (problema del canal de adquisición).

## Verificación

- [ ] Identificador de entidad único validado.
- [ ] La columna de fechas fue parseada a `DatetimeIndex` o `PeriodIndex` sin errores.
- [ ] La diagonal superior derecha del heatmap aparece correctamente vacía (sin actividad en el futuro).
- [ ] El periodo 0 es exactamente 100% para todas las cohortes.
