---
name: feature-engineering
description: Preprocesa features para modelado supervisado: encoding de categóricas (one-hot, ordinal, target), escalado (standard, minmax, robust), creación de polinomios e interacciones, discretización, drop de baja varianza, train/test split estratificado, y balanceo opcional de clases (undersample / class_weight). Úsese al inicio de ml-modeler, después de pandas-cleaning y antes de ml-modeling. Cada snippet trabaja sobre DataFrames y devuelve DataFrames / arrays con forma explícita, sin construir ColumnTransformer a mano.
---

# Feature Engineering

Preprocesamiento de features para modelado supervisado. Trabaja sobre
`pandas.DataFrame` y devuelve `DataFrame` o tuplas `(X_train, X_test,
y_train, y_test)` con forma consistente. **Nunca** se hace fit sobre el
dataset completo: el split es sagrado y precede a cualquier escalado o
encoding aprendido.

## Descripción general

Tres tipos de snippets:

1. **Encoding** — convertir categóricas a numéricas.
2. **Escalado y transformación** — poner features en una escala comparable.
3. **Split y balanceo** — separar train/test y manejar clases
   desbalanceadas.

Todos los snippets son funciones con argumentos explícitos; nunca se llama a
`ColumnTransformer.from_list(...)` con strings del usuario. La salida es
siempre tipada y devuelve el artefacto listo para `ml-modeling`.

## Cuándo usar

- Después de `pandas-cleaning` (sin nulos, dtypes consistentes).
- Después de `train_test_split_strat` (sagrado, siempre primero).
- Antes de `ml-modeling` (los modelos asumen features numéricas y, salvo
  árboles, escaladas).

No **usar** cuando:

- El usuario pide modelado no supervisado → fuera de alcance; este skill
  asume target supervisado.
- El dataset tiene >100k filas → preferir `polars` o `duckdb`; los
  snippets acá asumen pandas.
- Hay que manejar texto libre (NLP) → fuera de alcance; este skill cubre
  features tabulares.

## Snippets pre-aprobados — Encoding

### `encode_categorical(df, columns, method="onehot", drop_first=False)` — categóricas → numéricas

```python
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder

def encode_categorical(df, columns, method="onehot", drop_first=False, categories=None):
    """Convierte columnas categóricas a numéricas.

    method='onehot' -> columnas dummies (0/1) por categoría.
    method='ordinal' -> entero 0..k-1 según orden (útil para modelos
        basados en árboles; peligroso para lineales que asumen orden
        significativo).

    Devuelve (df_encoded, encoder) — el encoder debe guardarse junto al
    modelo final para invertir la transformación o aplicar a datos nuevos.
    """
    df = df.copy()
    if method == "onehot":
        enc = OneHotEncoder(sparse_output=False, drop="first" if drop_first else None,
                            handle_unknown="ignore")
        enc.fit(df[columns].astype(str))
        names = enc.get_feature_names_out(columns)
        out = pd.DataFrame(enc.transform(df[columns].astype(str)), columns=names, index=df.index)
        df = pd.concat([df.drop(columns=columns), out], axis=1)
    elif method == "ordinal":
        enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
        if categories is not None:
            enc.categories = categories  # tipo: ignore[attr-defined]
        enc.fit(df[columns].astype(str))
        df[columns] = enc.transform(df[columns].astype(str)).astype(int)
    else:
        raise ValueError(f"method debe ser 'onehot' u 'ordinal', recibido: {method}")
    return df, enc
```

### `drop_low_variance(df, threshold=0.0)` — eliminar columnas constantes o casi constantes

```python
from sklearn.feature_selection import VarianceThreshold

def drop_low_variance(df, threshold=0.0):
    """Elimina columnas con varianza <= threshold. Útil para one-hot
    con categorías raras (casi todas 0)."""
    selector = VarianceThreshold(threshold=threshold)
    selector.fit(df)
    kept = df.columns[selector.get_support()]
    return df[kept]
```

## Snippets pre-aprobados — Escalado

### `scale_numeric(df, columns, method="standard", fit_only=False)` — poner en escala comparable

```python
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

def scale_numeric(df, columns, method="standard", scaler=None):
    """Escala columnas numéricas. fit solo en train (fit_only=True solo
    fittea, devuelve el scaler; fit_only=False transforma inplace)."""
    df = df.copy()
    if scaler is None:
        if method == "standard":
            scaler = StandardScaler()
        elif method == "minmax":
            scaler = MinMaxScaler()
        elif method == "robust":
            scaler = RobustScaler()
        else:
            raise ValueError(f"method debe ser 'standard', 'minmax' o 'robust'")
        scaler.fit(df[columns])
    out = pd.DataFrame(scaler.transform(df[columns]), columns=columns, index=df.index)
    df[columns] = out
    return df, scaler
```

## Snippets pre-aprobados — Creación de features

### `polynomial_features(df, columns, degree=2, interaction_only=False)` — poly + interacciones

```python
from sklearn.preprocessing import PolynomialFeatures

def polynomial_features(df, columns, degree=2, interaction_only=False):
    """Genera poly features sobre `columns`. Devuelve (df_extended, poly).

    Cuidado: degree=3 sobre 10 features = 286 columnas. Usar con control.
    """
    pf = PolynomialFeatures(degree=degree, interaction_only=interaction_only, include_bias=False)
    pf.fit(df[columns])
    new_cols = pf.get_feature_names_out(columns)
    poly_block = pd.DataFrame(pf.transform(df[columns]), columns=new_cols, index=df.index)
    df = pd.concat([df.drop(columns=columns), poly_block], axis=1)
    return df, pf
```

### `bin_continuous(df, column, n_bins=5, strategy="quantile")` — discretizar

```python
from sklearn.preprocessing import KBinsDiscretizer

def bin_continuous(df, column, n_bins=5, strategy="quantile"):
    """Discretiza `column` en `n_bins` segmentos. Devuelve (df, discretizer)."""
    df = df.copy()
    disc = KBinsDiscretizer(n_bins=n_bins, strategy=strategy, encode="ordinal", subsample=None)
    disc.fit(df[[column]])
    df[f"{column}_binned"] = disc.transform(df[[column]]).astype(int)
    return df, disc
```

## Snippets pre-aprobados — Split

### `train_test_split_strat(X, y, test_size=0.2, random_state=42, stratify=None)` — split sagrado

```python
from sklearn.model_selection import train_test_split

def train_test_split_strat(X, y, test_size=0.2, random_state=42, stratify=None):
    """Split train/test. Si stratify es una Serie o array, estratifica por
    ella (de uso obligatorio para clasificación desbalanceada)."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=stratify,
    )
    # Reset indices para evitar alignment issues después de concat
    return (
        X_train.reset_index(drop=True),
        X_test.reset_index(drop=True),
        y_train.reset_index(drop=True),
        y_test.reset_index(drop=True),
    )
```

## Snippets pre-aprobados — Balanceo

### `balance_classes(X, y, method="class_weight", sampling_strategy="auto")` — manejar desbalance

```python
import numpy as np
import pandas as pd

def balance_classes(X, y, method="class_weight", sampling_strategy="auto", random_state=42):
    """Tres estrategias para clases desbalanceadas:

    method='class_weight' -> devuelve (X, y, {'class_weight': 'balanced'}).
        El usuario pasa el dict a LogisticRegression/RandomForest/GradientBoosting.
    method='undersample' -> submuestrea la clase mayor a `sampling_strategy`
        (proporción o número absoluto).
    method='oversample' -> sobremuestrea la clase menor (duplicación simple;
        para SMOTE real usar imblearn fuera de esta skill).

    Devuelve: para class_weight -> (X, y, kwargs);
              para sampleo -> (X_res, y_res, None).
    """
    if method == "class_weight":
        return X, y, {"class_weight": "balanced"}
    if method == "undersample":
        df = X.copy()
        df["__target__"] = y
        counts = df["__target__"].value_counts()
        if sampling_strategy == "auto":
            target_n = counts.min()
        elif isinstance(sampling_strategy, float):
            target_n = int(counts.max() * sampling_strategy)
        else:
            target_n = int(sampling_strategy)
        parts = []
        rng = np.random.default_rng(random_state)
        for cls, _ in counts.items():
            sub = df[df["__target__"] == cls]
            if len(sub) > target_n:
                sub = sub.sample(n=target_n, random_state=random_state)
            parts.append(sub)
        res = pd.concat(parts, axis=0).sample(frac=1, random_state=random_state).reset_index(drop=True)
        y_res = res.pop("__target__")
        return res, y_res, None
    if method == "oversample":
        df = X.copy()
        df["__target__"] = y
        counts = df["__target__"].value_counts()
        max_n = counts.max()
        parts = []
        rng = np.random.default_rng(random_state)
        for cls, _ in counts.items():
            sub = df[df["__target__"] == cls]
            if len(sub) < max_n:
                idx = rng.choice(sub.index, size=max_n - len(sub), replace=True)
                sub = pd.concat([sub, df.loc[idx]])
            parts.append(sub)
        res = pd.concat(parts, axis=0).sample(frac=1, random_state=random_state).reset_index(drop=True)
        y_res = res.pop("__target__")
        return res, y_res, None
    raise ValueError(f"method debe ser 'class_weight', 'undersample' u 'oversample'")
```

## Lista de verificación de orden

| Paso | Snippet | Cuándo |
|---|---|---|
| 0 | (split) | `train_test_split_strat` SIEMPRE primero — antes de cualquier scaler/encoder que tenga fit |
| 1 | (encoding) | `encode_categorical` sobre X_train y X_test con el encoder fiteado solo en train |
| 2 | (escalado) | `scale_numeric` igual: fit en train, transform en ambos |
| 3 | (opcional) | `polynomial_features`, `bin_continuous`, `drop_low_variance` después del escalado |
| 4 | (clasificación) | `balance_classes` ANTES del modelo si las clases están muy desbalanceadas |

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "El scaler lo aplico al dataset completo, después spliteo." | Data leakage: el scaler vio estadísticas del test set. Las métricas se inflan. |
| "LabelEncoder para esta categórica." | LabelEncoder asigna 0..k-1 en orden de aparición → el modelo cree que hay orden. Usar one-hot o target encoding. |
| "Tengo 30 features, le meto poly degree=3." | degree=3 sobre 30 features = 4960 columnas → memoria explotada. Limitar degree=2 y/o usar `interaction_only=True`. |
| "Accuracy es suficiente." | Accuracy en clasificación desbalanceada es engañosa: 99% con un modelo que siempre predice la clase mayor. Usar F1 o ROC-AUC. |
| "SMOTE va a resolver el desbalance." | SMOTE crea sintéticos por interpolación — pueden estar fuera de la distribución real si los features están muy correlacionados. Probar primero `class_weight`. |
| "No hace falta reset_index después de split." | Después de `train_test_split`, los índices son los originales; concatenar y unir con `__target__` puede alinear mal. Resetear. |

## Señales de alerta

- `columns` en `encode_categorical` contiene una columna con >50 categorías
  únicas → one-hot genera explosión; sugerir ordinal + target encoding o
  embedding (fuera de alcance).
- `scale_numeric` aplicado a una columna binaria (0/1) → la transforma a
  valores no binarios; excluirla de las columnas a escalar.
- `train_test_split_strat` sin `stratify` sobre clasificación → clases
  desbalanceadas pueden quedar con cero ejemplos en test.
- `balance_classes(method='oversample')` sobre dataset grande → memoria
  puede explotar; reportar el tamaño final.
- Pedido de "encoding del target" → usar `LabelEncoder` ad-hoc sobre `y`
  (no a través de esta skill); el target sí puede llevar LabelEncoder
  directamente.

## Verificación

- [ ] El split se hizo **antes** del escalado y del encoding con fit.
- [ ] El encoder y el scaler se fitean **solo** en train (verificar con
      `.fit(X_train)` y `.transform(X_test)`, no `.fit_transform(X_test)`).
- [ ] X_train y X_test tienen la misma cantidad y orden de columnas
      post-transformación.
- [ ] Si se usó `balance_classes`, el target final tiene la cardinalidad
      reportada.
- [ ] No se construyen `ColumnTransformer` o `Pipeline` con strings del
      usuario — siempre snippets pre-aprobados.
- [ ] Hay `random_state` explícito en split y en sampleo para
      reproducibilidad.
