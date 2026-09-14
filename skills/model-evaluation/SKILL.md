---
name: model-evaluation
description: Evalúa modelos supervisados (clasificación y regresión) con métricas estándar, matrices de confusión, curvas ROC/PR, análisis de residuos, feature importances y learning curves para detectar overfitting. Úsese después de ml-modeling, sobre el test set sagrado, con la misma forma de retorno que statistical-testing (dict con campos nombrados) para conectar directo con insight-synthesis.
---

# Model Evaluation

Métricas y diagnósticos para modelos entrenados con `ml-modeling`. Cada
snippet devuelve un `dict` con `test` / `metric` / `value` / `aux` para
mantener la misma forma que `statistical-testing` (así `insight-synthesis`
puede consumir ambos sin código adicional).

## Descripción general

Tres tipos de snippets:

1. **Métricas globales** — accuracy, F1, ROC-AUC (clasificación); MAE,
   RMSE, R², MAPE (regresión).
2. **Diagnósticos** — matriz de confusión, classification report, análisis
   de residuos, curvas ROC/PR.
3. **Inspección de modelo** — feature importances, learning curves.

El test set se usa **una vez** al final; todo lo demás se hace con CV o
train set.

## Cuándo usar

- Después de `ml-modeling` con el modelo ya fiteado.
- Sobre `X_test`, `y_test` (test set sagrado).
- Para comparar 2+ modelos sobre el mismo test set con la misma métrica.

No **usar** cuando:

- El modelo no fue entrenado con los snippets de `ml-modeling`.
- El test set ya se usó para elegir hiperparámetros (data leakage).
- El usuario pide deployment o monitoreo → fuera de alcance; este skill
  evalúa, no sirve.

## Snippets pre-aprobados — Métricas de clasificación

### `classification_metrics(y_true, y_pred, y_proba=None)` — métricas globales

```python
import numpy as np
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, log_loss, balanced_accuracy_score,
)

def classification_metrics(y_true, y_pred, y_proba=None, average="binary"):
    """Devuelve un dict con métricas de clasificación.

    y_proba: probabilidades de la clase positiva (shape (n,) o (n, n_classes)).
    average: 'binary' (default), 'micro', 'macro', 'weighted'.

    Devuelve dict con todas las métricas + label interpretable.
    """
    out = {
        "test": "classification_metrics",
        "n": int(len(y_true)),
        "accuracy":         float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy":float(balanced_accuracy_score(y_true, y_pred)),
        "precision":        float(precision_score(y_true, y_pred, average=average, zero_division=0)),
        "recall":           float(recall_score(y_true, y_pred, average=average, zero_division=0)),
        "f1":               float(f1_score(y_true, y_pred, average=average, zero_division=0)),
    }
    if y_proba is not None:
        try:
            if y_proba.ndim == 1 or (hasattr(y_proba, "shape") and y_proba.shape[1] == 2):
                out["roc_auc"] = float(roc_auc_score(y_true, y_proba if y_proba.ndim == 1 else y_proba[:, 1]))
            else:
                out["roc_auc"] = float(roc_auc_score(y_true, y_proba, multi_class="ovr", average=average))
        except ValueError as e:
            out["roc_auc"] = None
            out["roc_auc_error"] = str(e)
        try:
            out["log_loss"] = float(log_loss(y_true, y_proba))
        except ValueError:
            out["log_loss"] = None
    return out
```

### `confusion_matrix_report(y_true, y_pred, labels=None)` — matriz + por-clase

```python
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report

def confusion_matrix_report(y_true, y_pred, labels=None):
    """Devuelve dict con matriz (DataFrame) + reporte (dict por clase)."""
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    if labels is None:
        labels = sorted(np.unique(np.concatenate([np.asarray(y_true), np.asarray(y_pred)])))
    cm_df = pd.DataFrame(cm, index=[f"true_{l}" for l in labels], columns=[f"pred_{l}" for l in labels])
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    return {
        "test": "confusion_matrix",
        "matrix": cm_df,
        "per_class": {k: v for k, v in report.items() if k not in ("accuracy", "macro avg", "weighted avg")},
        "macro_avg": report.get("macro avg", {}),
        "weighted_avg": report.get("weighted avg", {}),
        "labels": [str(l) for l in labels],
        "n": int(len(y_true)),
    }
```

## Snippets pre-aprobados — Métricas de regresión

### `regression_metrics(y_true, y_pred)` — métricas globales

```python
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def regression_metrics(y_true, y_pred):
    """MAE, MSE, RMSE, R², MAPE. Devuelve dict."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    eps = 1e-9
    mape = float(np.mean(np.abs((y_true - y_pred) / np.where(np.abs(y_true) < eps, eps, y_true))) * 100)
    return {
        "test": "regression_metrics",
        "n": int(len(y_true)),
        "mae":      float(mean_absolute_error(y_true, y_pred)),
        "mse":      float(mean_squared_error(y_true, y_pred)),
        "rmse":     float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "r2":       float(r2_score(y_true, y_pred)),
        "mape_pct": mape,
    }
```

### `residual_analysis(y_true, y_pred)` — diagnóstico para regresión

```python
import numpy as np
import pandas as pd

def residual_analysis(y_true, y_pred):
    """Devuelve DataFrame con y_true, y_pred, residual, residual_z.
    Útil para detectar heterocedasticidad o patrones no lineales."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    res = y_true - y_pred
    sd = float(res.std(ddof=1)) if len(res) > 1 else 0.0
    z = (res - res.mean()) / sd if sd > 0 else np.zeros_like(res)
    df = pd.DataFrame({
        "y_true":      y_true,
        "y_pred":      y_pred,
        "residual":    res,
        "residual_z":  z,
    })
    return {
        "test": "residual_analysis",
        "data": df,
        "residual_mean": float(res.mean()),
        "residual_std":  sd,
        "outliers_n":    int((np.abs(z) > 3).sum()),
        "n":             int(len(y_true)),
    }
```

## Snippets pre-aprobados — Curvas (para graficar en `viz-patterns`)

### `roc_curve_data(y_true, y_proba)` — puntos para graficar ROC

```python
import numpy as np
from sklearn.metrics import roc_curve

def roc_curve_data(y_true, y_proba):
    """Devuelve dict con fpr, tpr, thresholds (arrays)."""
    fpr, tpr, thr = roc_curve(y_true, y_proba)
    return {
        "test": "roc_curve",
        "fpr": fpr.tolist(),
        "tpr": tpr.tolist(),
        "thresholds": thr.tolist(),
        "n": int(len(y_true)),
    }
```

### `precision_recall_curve_data(y_true, y_proba)` — puntos para PR

```python
import numpy as np
from sklearn.metrics import precision_recall_curve

def precision_recall_curve_data(y_true, y_proba):
    """Devuelve dict con precision, recall, thresholds."""
    prec, rec, thr = precision_recall_curve(y_true, y_proba)
    return {
        "test": "precision_recall_curve",
        "precision": prec.tolist(),
        "recall":    rec.tolist(),
        "thresholds": thr.tolist(),
        "n": int(len(y_true)),
    }
```

## Snippets pre-aprobados — Inspección de modelo

### `feature_importance(model, feature_names, top_n=20)` — qué features pesan

```python
import pandas as pd

def feature_importance(model, feature_names, top_n=20):
    """Extrae feature_importances_ (árboles / GBM) o coef_ (lineales).
    Para lineales, devuelve el valor absoluto de los coeficientes.
    Devuelve DataFrame con feature, importance, rank, normalizado a 100."""
    if hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
        source = "feature_importances_"
    elif hasattr(model, "coef_"):
        coef = model.coef_
        imp = (coef ** 2).sum(axis=0) if coef.ndim > 1 else np.abs(coef)
        source = "abs_coef_squared" if coef.ndim > 1 else "abs_coef"
    else:
        raise ValueError("El modelo no expone ni feature_importances_ ni coef_")
    total = float(imp.sum())
    df = pd.DataFrame({
        "feature":    list(feature_names),
        "importance": imp,
    })
    df["importance_pct"] = (df["importance"] / total * 100) if total > 0 else 0.0
    df = df.sort_values("importance", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return {
        "test": "feature_importance",
        "data": df.head(top_n),
        "source": source,
        "n_features": int(len(feature_names)),
        "top_n": int(top_n),
    }
```

### `learning_curve_data(model, X, y, train_sizes=None, cv=5, scoring=None)` — diagnóstico de overfitting

```python
import numpy as np
from sklearn.model_selection import learning_curve

def learning_curve_data(model, X, y, train_sizes=None, cv=5, scoring=None, n_jobs=-1):
    """Devuelve dict con train_sizes, train_mean, train_std, test_mean, test_std.

    Si el gap entre train_mean y test_mean crece con train_sizes -> overfitting.
    Si ambos convergen a un valor bajo -> underfitting (probar modelo más
    complejo o features).
    """
    if train_sizes is None:
        train_sizes = np.linspace(0.1, 1.0, 5)
    sizes, train_scores, test_scores = learning_curve(
        model, X, y, cv=cv, train_sizes=train_sizes,
        scoring=scoring, n_jobs=n_jobs, random_state=42,
    )
    return {
        "test": "learning_curve",
        "train_sizes":       sizes.tolist(),
        "train_score_mean":  train_scores.mean(axis=1).tolist(),
        "train_score_std":   train_scores.std(axis=1).tolist(),
        "test_score_mean":   test_scores.mean(axis=1).tolist(),
        "test_score_std":    test_scores.std(axis=1).tolist(),
        "cv":                int(cv),
        "scoring":           scoring,
        "n":                 int(len(X)),
    }
```

## Lista de verificación — qué reportar

| Tarea | Métrica primaria | Métricas secundarias | Diagnósticos |
|---|---|---|---|
| Clasificación balanceada | accuracy | precision, recall, F1 | confusion_matrix |
| Clasificación desbalanceada | ROC-AUC o F1 | precision, recall | confusion_matrix, roc_curve, pr_curve |
| Regresión | RMSE o MAE | R², MAPE | residual_analysis, learning_curve |
| Cualquier modelo | — | — | feature_importance, learning_curve |

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "Accuracy 0.99 está perfecto." | Si la clase mayoritaria es 99%, accuracy es trivial. F1 / ROC-AUC capturan más señal. |
| "ROC-AUC alto, modelo listo." | ROC-AUC alta no implica buena calibration; el modelo puede rankear bien pero errar las probabilidades. Chequear `log_loss`. |
| "RMSE es bajo, modelo bueno." | RMSE es sensible a outliers; si hay uno con error 1000, infla todo. Reportar MAE también. |
| "Las features más importantes son las primeras que se me ocurrieron." | Verificar con permutation importance (fuera de v2) o `feature_importance` con un modelo in-bag. |
| "El learning curve muestra que el modelo aprende más con más datos." | Eso es señal de underfitting — más datos no van a arreglar arquitectura insuficiente. |
| "Cross-validation ya dijo que el modelo generaliza, no hace falta test set." | Test set es el **único** estimador insesgado. CV mide varianza del train, no generalización real. |

## Señales de alerta

- `accuracy > 0.99` en clasificación sin verificar balance de clases →
  probable leakage o accuracy trivial.
- `roc_auc < 0.6` → modelo apenas mejor que random; replantear features.
- `r2 < 0` en test → modelo peor que la media; cambiar features o modelo.
- `residual_std > 2 * std(y_train)` → heterocedasticidad severa;
  transformar target (log) o usar modelo con varianza explícita.
- `learning_curve`: gap train-test creciente con train_sizes → overfitting;
  reducir complejidad o aumentar regularización.
- Pedido de "matriz de correlación entre y_pred y y_true" → no es una
  métrica útil; reportar `r2` directamente.

## Verificación

- [ ] Las métricas se calcularon **una sola vez** sobre el test set.
- [ ] La métrica primaria es la declarada al inicio del flujo (no se
      cambió sobre la marcha para inflar el reporte).
- [ ] En clasificación: accuracy + F1 + ROC-AUC + matriz de confusión.
- [ ] En regresión: MAE + RMSE + R² + análisis de residuos.
- [ ] `feature_importance` devuelve al menos top-5 features, no solo la
      primera.
- [ ] `learning_curve` se incluye cuando hay sospecha de overfitting (gap
      train-CV > 0.1) — no siempre, pero documentar cuando se omitió.
- [ ] El reporte no mezcla métricas de train y test en la misma fila.
