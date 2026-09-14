---
name: ml-modeling
description: Entrena modelos supervisados pre-aprobados (regresión lineal con regularización, regresión logística, árbol de decisión, random forest, gradient boosting sklearn) y evalúa con cross-validation. Úsese después de feature-engineering y antes de model-evaluation. Cada snippet devuelve un modelo sklearn listo para `.predict` / `.predict_proba` con hiperparámetros explícitos y random_state para reproducibilidad. Sin búsqueda de hiperparámetros (grid/random search): eso queda como extensión documentada.
---

# ML Modeling

Entrenamiento de modelos supervisados con `scikit-learn`. Cada snippet
devuelve un estimador fiteado listo para evaluar con `model-evaluation`.
Hiperparámetros siempre explícitos; `random_state` siempre seteado.

## Descripción general

Tres familias de modelos, una utility de cross-validation, una utility de
fit + métricas de train:

- **Lineales**: `LinearRegression` (con regularización opcional vía
  `Ridge`), `LogisticRegression`. Son el baseline — siempre probar primero.
- **Basados en árboles**: `DecisionTree`, `RandomForest`, `GradientBoosting`
  (sklearn). Capturan no linealidad e interacciones sin preprocesamiento
  adicional (no necesitan escalado).
- **Cross-validation**: utility para estimar varianza de la métrica antes
  de tocar el test set.

Ningún snippet hace `.fit_transform` ni `ColumnTransformer.from_list(...)`
con strings del usuario — el preprocesamiento previo es responsabilidad de
`feature-engineering`.

## Cuándo usar

- Después de `feature-engineering` (features ya encodeadas + escaladas
  opcionalmente).
- Antes de `model-evaluation` (test set sagrado: solo se evalúa al final).
- Para comparar 2+ modelos en el mismo split y elegir el mejor por CV.

No **usar** cuando:

- El target no existe o es no supervisado → fuera de alcance.
- Hay que hacer búsqueda de hiperparámetros (`GridSearchCV`,
  `RandomizedSearchCV`) → se puede llamar, pero como bloque explícito
  documentado, no como snippet pre-aprobado. Mantener el alcance de esta
  skill acotado.
- Hay que entrenar deep learning (Keras, PyTorch) → fuera de alcance.
- El dataset tiene >1M filas → considerar `cuML` o sampleo; los snippets
  usan sklearn CPU.

## Snippets pre-aprobados — Modelos lineales

### `train_linear_regression(X_train, y_train, alpha=1.0, type="ridge")` — regresión lineal con regularización

```python
from sklearn.linear_model import LinearRegression, Ridge, Lasso

def train_linear_regression(X_train, y_train, alpha=1.0, type="ridge"):
    """type='ols' (sin regularización), 'ridge' (L2) o 'lasso' (L1).
    alpha solo aplica a ridge/lasso."""
    if type == "ols":
        model = LinearRegression()
    elif type == "ridge":
        model = Ridge(alpha=alpha, random_state=42)
    elif type == "lasso":
        model = Lasso(alpha=alpha, random_state=42)
    else:
        raise ValueError(f"type debe ser 'ols', 'ridge' o 'lasso'")
    model.fit(X_train, y_train)
    return model
```

### `train_logistic_regression(X_train, y_train, C=1.0, class_weight=None)` — clasificación binaria o multiclass

```python
from sklearn.linear_model import LogisticRegression

def train_logistic_regression(X_train, y_train, C=1.0, class_weight=None, max_iter=1000):
    """Logistic regression. C = inverse regularization strength.
    class_weight='balanced' para clases desbalanceadas."""
    model = LogisticRegression(
        C=C, class_weight=class_weight, max_iter=max_iter,
        random_state=42, solver="lbfgs",
    )
    model.fit(X_train, y_train)
    return model
```

## Snippets pre-aprobados — Árboles

### `train_decision_tree(X_train, y_train, task="classification", max_depth=None, class_weight=None)` — árbol

```python
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

def train_decision_tree(X_train, y_train, task="classification", max_depth=None,
                        class_weight=None, min_samples_leaf=1):
    """task='classification' o 'regression'. max_depth=None crece hasta
    pureza total (casi siempre overfit). Sugerir max_depth=3..8."""
    if task == "classification":
        model = DecisionTreeClassifier(
            max_depth=max_depth, class_weight=class_weight,
            min_samples_leaf=min_samples_leaf, random_state=42,
        )
    elif task == "regression":
        model = DecisionTreeRegressor(
            max_depth=max_depth, min_samples_leaf=min_samples_leaf, random_state=42,
        )
    else:
        raise ValueError("task debe ser 'classification' o 'regression'")
    model.fit(X_train, y_train)
    return model
```

### `train_random_forest(X_train, y_train, task="classification", n_estimators=100, max_depth=None, class_weight=None)` — bosque

```python
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

def train_random_forest(X_train, y_train, task="classification", n_estimators=100,
                        max_depth=None, class_weight=None, min_samples_leaf=1):
    """Random Forest. Robusto a overfitting; más caro que un árbol solo."""
    if task == "classification":
        model = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth,
            class_weight=class_weight, min_samples_leaf=min_samples_leaf,
            n_jobs=-1, random_state=42,
        )
    elif task == "regression":
        model = RandomForestRegressor(
            n_estimators=n_estimators, max_depth=max_depth,
            min_samples_leaf=min_samples_leaf, n_jobs=-1, random_state=42,
        )
    else:
        raise ValueError("task debe ser 'classification' o 'regression'")
    model.fit(X_train, y_train)
    return model
```

### `train_gradient_boosting(X_train, y_train, task="classification", n_estimators=100, learning_rate=0.1, max_depth=3)` — GBM

```python
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor

def train_gradient_boosting(X_train, y_train, task="classification",
                            n_estimators=100, learning_rate=0.1, max_depth=3):
    """Gradient Boosting sklearn (no XGBoost/LightGBM — esos son opcionales
    fuera de v2). Típicamente el mejor modelo tabular sin tuning."""
    if task == "classification":
        model = GradientBoostingClassifier(
            n_estimators=n_estimators, learning_rate=learning_rate,
            max_depth=max_depth, random_state=42,
        )
    elif task == "regression":
        model = GradientBoostingRegressor(
            n_estimators=n_estimators, learning_rate=learning_rate,
            max_depth=max_depth, random_state=42,
        )
    else:
        raise ValueError("task debe ser 'classification' o 'regression'")
    model.fit(X_train, y_train)
    return model
```

## Snippets pre-aprobados — Cross-validation y fit reporting

### `cross_validate_model(model, X, y, cv=5, scoring=None, task="classification")` — CV estandarizada

```python
import numpy as np
from sklearn.model_selection import cross_validate

def cross_validate_model(model, X, y, cv=5, scoring=None, task="classification"):
    """Cross-validation estandarizada sobre train set.

    scoring default:
      - clasificación: 'accuracy' (pero el agente debe cambiarla a 'f1'
        o 'roc_auc' si las clases están desbalanceadas).
      - regresión: 'r2'.

    Devuelve dict con 'mean', 'std', 'fold_scores', 'fit_time_mean_s'.
    """
    if scoring is None:
        scoring = "accuracy" if task == "classification" else "r2"
    res = cross_validate(model, X, y, cv=cv, scoring=scoring,
                         return_train_score=True, n_jobs=-1)
    return {
        "test_score_mean":  float(np.mean(res["test_score"])),
        "test_score_std":   float(np.std(res["test_score"])),
        "test_scores":      [float(s) for s in res["test_score"]],
        "train_score_mean": float(np.mean(res["train_score"])),
        "train_score_std":  float(np.std(res["train_score"])),
        "fit_time_mean_s":  float(np.mean(res["fit_time"])),
        "scoring":          scoring,
        "cv":               int(cv),
    }
```

### `train_baseline_logreg(X_train, y_train, task="classification")` — baseline listo

```python
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.dummy import DummyClassifier, DummyRegressor

def train_baseline(task, X_train, y_train, strategy="most_frequent"):
    """Baseline honesto: para clasificación, predice la clase mayor;
    para regresión, predice la media. Cualquier modelo 'real' debe
    superar este baseline en CV."""
    if task == "classification":
        m = DummyClassifier(strategy=strategy, random_state=42)
    elif task == "regression":
        m = DummyRegressor(strategy="mean")
    else:
        raise ValueError("task debe ser 'classification' o 'regression'")
    m.fit(X_train, y_train)
    return m
```

## Lista de verificación de comparación

| Modelo | Cuándo probarlo | Costo |
|---|---|---|
| `train_baseline` (dummy) | **Siempre** primero — ancla mínima | bajo |
| `train_linear_regression` / `train_logistic_regression` | **Siempre** segundo — primer modelo real, interpretable | bajo |
| `train_decision_tree` (max_depth=3..8) | Para entender la estructura, interacciones simples | bajo |
| `train_random_forest` | Default razonable; robusto a overfit; sin escalado | medio |
| `train_gradient_boosting` | Mejor accuracy típica; más lento; sin escalado | medio-alto |

Comparar siempre con `cross_validate_model` antes de tocar el test set.

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "Salteamos el baseline, vamos directo a RF." | Sin baseline, no se sabe si RF está aprendiendo o si cualquier cosa lo supera. Siempre dummy primero. |
| "Más estimadores siempre es mejor." | Más estimadores = más costo. Knee point típico: 100-200. Subir solo si CV mejora marginalmente. |
| "Random Forest no necesita escalado." | Correcto (basado en árboles), pero no quiere decir que nunca necesite preprocesamiento — sigue necesitando encoding de categóricas. |
| "Gradient Boosting siempre le gana a Random Forest." | No siempre: con features ruidosas o pocas filas, RF puede generalizar mejor. Probar ambos. |
| "Uso XGBoost." | XGBoost no es dependencia de v2. Si está instalado, se puede usar fuera de los snippets — pero sklearn GBM es la base comparable. |
| "Class_weight solo para clasificación." | También aplica a `RandomForestClassifier` y `GradientBoostingClassifier` (no a `Regressor`); registrarse siempre que las clases estén desbalanceadas. |

## Señales de alerta

- `n_train < 500` con más de 50 features → cualquier modelo va a overfitear;
  podar features primero (volver a `feature-engineering`).
- CV `test_score_std > 0.1` → dataset chico o features ruidosas; cambiar
  CV a `StratifiedKFold` explícito o reportar alta varianza.
- `train_score` >> `test_score` en CV → overfitting; reducir
  `max_depth` o `n_estimators`, o aumentar regularización.
- `train_baseline` con accuracy/F1 razonable pero todos los modelos en
  el mismo número → el target tiene poco señal; replantear el feature set.
- Pedido de XGBoost/LightGBM → instalarlos como dep extra fuera de v2,
  o usar `GradientBoosting` como sustituto.

## Verificación

- [ ] Todos los modelos usan `random_state=42` (reproducibilidad).
- [ ] Se entrenó al menos un baseline antes del primer modelo real.
- [ ] Cada modelo reporta `cross_validate_model` con mean ± std, no
      métrica puntual.
- [ ] `train_score_mean - test_score_mean < 0.1` para el modelo elegido
      (o documentar el gap de overfitting).
- [ ] El test set no se usó para elegir hiperparámetros ni modelo.
- [ ] No se construyó ningún modelo "a mano" — todos pasaron por un
      snippet pre-aprobado.
