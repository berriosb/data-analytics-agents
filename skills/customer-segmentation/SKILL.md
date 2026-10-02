---
name: customer-segmentation
description: Técnicas no supervisadas de segmentación analítica de clientes y clustering sobre datos tabulares: segmentación RFM (Recency, Frequency, Monetary) con quintiles y scoring, K-Means clustering con optimización de k (método del codo / WCSS y Silhouette Score), perfilado de clusters y proyección PCA 2D con visualización en scatter Plotly. Úsese cuando el usuario quiera segmentar clientes, agrupar observaciones por comportamiento o descubrir perfiles sin target supervisado.
---

# Customer Segmentation

Especializada en análisis exploratorio y segmentación no supervisada de clientes y
observaciones tabulares. Cubre el espectro desde la heurística de negocio clásica
(**RFM Scoring**) hasta el clustering estadístico (**K-Means + PCA**) con interpretación
rigurosa.

## Descripción general

La analítica de clientes busca dividir una base heterogénea en grupos accionables.
Esta skill provee snippets probados para:

1. **Segmentación RFM (Recency, Frequency, Monetary)**:
   - Medir días desde la última compra (R), cantidad de compras (F) y valor total gastado (M).
   - Asignar quintiles (1–5) y clasificar en arquetipos de negocio (*Champions, Loyal, At Risk, Can't Lose Them, Lost*).
2. **K-Means Clustering con optimización de $k$**:
   - Escalado previo de variables con `StandardScaler`.
   - Evaluación combinada de inercia (método del codo) y *Silhouette Score*.
3. **Perfilado e interpretación de clusters**:
   - Resumen estadístico (medias y medianas) de cada segmento para darles nombre de negocio.
4. **Proyección y visualización 2D con PCA**:
   - Reducción a 2 componentes principales para inspeccionar la separabilidad de los grupos en Plotly.

## Cuándo usar

- Cuando el dataset contiene historial transaccional de usuarios o múltiples features de comportamiento.
- Cuando el usuario pregunta:
  - "¿Cómo puedo segmentar a mis clientes según su valor y frecuencia?"
  - "Hacé una segmentación RFM."
  - "¿Cuántos clusters naturales hay en estos datos?"
  - "¿Cuáles son los perfiles de usuarios que tenemos?"
- En `data-explorer` o `reporting-analyst` para análisis de negocio no supervisado.

No **usar** cuando:

- Hay una variable objetivo definida que se quiere predecir (ej. predecir churn o default) → enrutar a `ml-modeler`.
- El dataset tiene < 50 observaciones (clustering inestable).

## Snippets pre-aprobados (Pandas + Scikit-Learn + Plotly)

### 1. `calculate_rfm_segments(df, customer_id_col, date_col, amount_col, reference_date=None)`

```python
import pandas as pd
import numpy as np

def calculate_rfm_segments(df, customer_id_col, date_col, amount_col, reference_date=None):
    """Calcula métricas RFM, asigna quintiles y categoriza en arquetipos de clientes."""
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[customer_id_col, date_col, amount_col])

    if reference_date is None:
        reference_date = df[date_col].max() + pd.Timedelta(days=1)
    else:
        reference_date = pd.to_datetime(reference_date)

    # Agregación a nivel cliente
    rfm = df.groupby(customer_id_col).agg(
        Recency=(date_col, lambda d: (reference_date - d.max()).days),
        Frequency=(date_col, "count"),
        Monetary=(amount_col, "sum"),
    ).reset_index()

    # Asignar quintiles 1-5 (R invertido: menor recencia = mayor score)
    rfm["R_Score"] = pd.qcut(rfm["Recency"], q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["F_Score"] = pd.qcut(rfm["Frequency"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["M_Score"] = pd.qcut(rfm["Monetary"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int)

    rfm["RFM_Score"] = rfm["R_Score"].astype(str) + rfm["F_Score"].astype(str) + rfm["M_Score"].astype(str)

    # Mapeo a arquetipos de negocio
    def map_segment(row):
        r, f = row["R_Score"], row["F_Score"]
        if r >= 4 and f >= 4:
            return "Champions"
        if r >= 3 and f >= 3:
            return "Loyal Customers"
        if r >= 4 and f <= 2:
            return "Promising / Recent"
        if r <= 2 and f >= 4:
            return "At Risk / Can't Lose"
        if r <= 2 and f <= 2:
            return "Hibernating / Lost"
        return "Need Attention"

    rfm["Segment"] = rfm.apply(map_segment, axis=1)

    summary = rfm.groupby("Segment").agg(
        Count=(customer_id_col, "count"),
        Mean_Recency=("Recency", "mean"),
        Mean_Frequency=("Frequency", "mean"),
        Mean_Monetary=("Monetary", "mean"),
        Total_Monetary=("Monetary", "sum"),
    ).reset_index()
    summary["Pct_Customers"] = summary["Count"] / summary["Count"].sum() * 100.0
    summary["Pct_Revenue"] = summary["Total_Monetary"] / summary["Total_Monetary"].sum() * 100.0

    return {
        "rfm_table": rfm,
        "segment_summary": summary.sort_values("Total_Monetary", ascending=False),
    }
```

### 2. `tune_kmeans_clusters(X, k_range=range(2, 8), random_state=42)`

```python
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

def tune_kmeans_clusters(X, k_range=range(2, 8), random_state=42):
    """Evalúa múltiples valores de k usando Inercia (codo) y Silhouette Score."""
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    results = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=random_state, n_init=10)
        labels = km.fit_predict(X_scaled)
        sil = float(silhouette_score(X_scaled, labels))
        inertia = float(km.inertia_)
        results.append({
            "k": k,
            "inertia": inertia,
            "silhouette": sil,
        })

    eval_df = pd.DataFrame(results)
    best_k = int(eval_df.loc[eval_df["silhouette"].idxmax()]["k"])

    return {
        "eval_df": eval_df,
        "recommended_k": best_k,
        "scaler": scaler,
    }
```

### 3. `fit_and_profile_clusters(X, n_clusters, scaler=None, random_state=42)`

```python
def fit_and_profile_clusters(X, n_clusters, scaler=None, random_state=42):
    """Ajusta K-Means con k elegido y produce el perfil de medias por cluster."""
    if scaler is None:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
    else:
        X_scaled = scaler.transform(X)

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = km.fit_predict(X_scaled)

    df_clustered = X.copy()
    df_clustered["Cluster"] = [f"Cluster_{c}" for c in labels]

    profile = df_clustered.groupby("Cluster").agg(["mean", "median", "count"])
    return {
        "clustered_data": df_clustered,
        "labels": labels,
        "profile": profile,
        "model": km,
        "scaled_data": X_scaled,
    }
```

### 4. `plot_pca_cluster_projection(X_scaled, labels, title="Proyección 2D de Clusters (PCA)")`

```python
from sklearn.decomposition import PCA
import plotly.express as px

def plot_pca_cluster_projection(X_scaled, labels, title="Proyección 2D de Clusters (PCA)"):
    """Reduce features a 2D y genera visualización interactiva Plotly."""
    pca = PCA(n_components=2, random_state=42)
    components = pca.fit_transform(X_scaled)
    var_explained = pca.explained_variance_ratio_

    plot_df = pd.DataFrame({
        "PCA_1": components[:, 0],
        "PCA_2": components[:, 1],
        "Cluster": [f"Cluster {c}" for c in labels],
    })

    fig = px.scatter(
        plot_df,
        x="PCA_1",
        y="PCA_2",
        color="Cluster",
        title=f"{title} (Varianza explicada: {var_explained.sum()*100:.1f}%)",
        labels={
            "PCA_1": f"PC 1 ({var_explained[0]*100:.1f}% var)",
            "PCA_2": f"PC 2 ({var_explained[1]*100:.1f}% var)",
        },
        opacity=0.8,
    )
    fig.update_layout(template="plotly_white")
    return fig
```

## Señales de alerta

- **Clustering sin escalar**: Si `Monetary` tiene valores en miles y `Frequency` en unidades, `Monetary` dominará el 99% de la distancia euclídea sin `StandardScaler`.
- **Elegir $k$ solo por inercia**: La inercia siempre baja al aumentar $k$; chequear siempre el pico en `silhouette_score`.
- **Silhouette < 0.25**: Indica estructura de clusters débil o datos uniformemente distribuidos. No sobre-interpretar agrupaciones forzadas.

## Verificación

- [ ] Las variables numéricas fueron escaladas con `StandardScaler`.
- [ ] No se incluyeron identificadores únicos (`user_id`) como features de clustering.
- [ ] Cada cluster tiene una interpretación analítica clara basada en su perfil de medias/medianas.
