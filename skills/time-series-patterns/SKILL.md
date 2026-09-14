---
name: time-series-patterns
description: Análisis y transformación de series temporales tabulares (DatetimeIndex, resampling, rolling stats, lags, descomposición estacional, test de estacionariedad ADF, autocorrelación ACF/PACF, detección de periodicidad y forecasting naive). Úsese cuando una columna datetime es la dimensión de análisis y el usuario pide tendencia, estacionalidad, comparación entre periodos, o forecast a corto plazo. Cubre el hueco que statistical-testing deja explícitamente fuera ("series temporales con autocorrelación").
---

# Time Series Patterns

Dos niveles de snippets:

- **Lite (pandas + numpy solamente)** — 9 snippets para el 80% del EDA de
  series temporales: configuración del índice, resampling, rolling stats,
  lags, detección de periodicidad, comparación entre periodos, forecasting
  naive.
- **Full (lite + `statsmodels`)** — 4 snippets adicionales para análisis más
  profundo: descomposición estacional (clásica y STL), test de
  estacionariedad (Augmented Dickey-Fuller), autocorrelación y
  autocorrelación parcial (ACF / PACF).

Cada snippet devuelve una forma de retorno explícita y consistente. La skill
no ajusta modelos supervisados ni hace predicción fuera de muestra más allá
de los métodos naive.

## Descripción general

Trabaja sobre `pandas.Series` con `DatetimeIndex`. Si los datos están en un
`DataFrame` con una columna temporal separada, el primer snippet
(`setup_datetime_index`) los deja listos. Después, los demás snippets son
todos sobre `Series` indexadas por tiempo.

Las salidas se diseñan para conectarse con `viz-patterns` (las series
descompuestas encajan en `line facetado`) y con `insight-synthesis` (los
diccionarios de tests tienen la misma forma que `statistical-testing`).

## Cuándo usar

- Cuando hay una columna datetime que es la dimensión de análisis
  ("revenue por mes", "usuarios activos por día", "tickets por hora").
- Cuando el usuario pide explícitamente "tendencia", "estacionalidad",
  "forecast", "predicción", "comparar este mes contra el anterior".
- Como paso entre `pandas-cleaning` y `viz-patterns` cuando la
  visualización final necesita resampling o rolling (la línea directa de
  filas crudas produce ruido).
- Después de `statistical-testing`, cuando una "diferencia significativa"
  entre periodos en realidad es una serie con autocorrelación (los tests
  paramétricos asumen independencia y pueden dar p-values falsos).

No **usar** cuando:

- El dataset no tiene dimensión temporal.
- El usuario pide modelado predictivo supervisado (clasificación,
  regresión con features exógenas) → fuera de alcance; enrutar a la v2 de
  ML cuando exista.
- La frecuencia objetivo es sub-segundo y el dataset tiene >10M puntos →
  preferir muestreo + `statsmodels` con cuidado, o `polars`/`duckdb`.
- El usuario pide detección de anomalías (novelty / change-point detection
  formal) → fuera de alcance para esta skill.

## Snippets pre-aprobados — Tier 1 (lite, pandas + numpy)

### `setup_datetime_index(df, time_col, drop=True, sort=True)` — preparar la serie

```python
import pandas as pd
import numpy as np

def setup_datetime_index(df, time_col, drop=True, sort=True):
    """Convierte time_col a DatetimeIndex, lo asigna como índice del df."""
    df = df.copy()
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    bad = df[time_col].isna().sum()
    if bad:
        print(f"[time-series] {int(bad)} filas con {time_col} no parseable; descartadas")
        df = df.dropna(subset=[time_col])
    if sort:
        df = df.sort_values(time_col)
    df = df.set_index(time_col)
    if drop and df.columns.size == 1:
        df = df.iloc[:, 0]
    return df
```

### `resample_series(s, rule, agg="mean")` — cambiar granularidad

```python
def resample_series(s, rule, agg="mean"):
    """Resamplea a 'D' / 'W' / 'M' / 'Q' / 'Y' / 'H'. Devuelve Series."""
    if not isinstance(s.index, pd.DatetimeIndex):
        raise ValueError("resample_series requiere DatetimeIndex")
    if agg in ("mean", "sum", "min", "max", "median", "std", "first", "last"):
        return s.resample(rule).agg(agg)
    # agg puede ser dict-like {"col": func} o lista de funciones
    return s.resample(rule).agg(agg)
```

### `rolling_stats(s, window, stats=("mean",), min_periods=None)` — ventana móvil

```python
def rolling_stats(s, window, stats=("mean",), min_periods=None):
    """Rolling mean/std/median/min/max sobre la serie. Devuelve DataFrame."""
    if min_periods is None:
        min_periods = max(1, window // 2)
    rs = s.rolling(window=window, min_periods=min_periods)
    cols = {}
    if "mean" in stats:   cols["mean"]   = rs.mean()
    if "std" in stats:    cols["std"]    = rs.std()
    if "median" in stats: cols["median"] = rs.median()
    if "min" in stats:    cols["min"]    = rs.min()
    if "max" in stats:    cols["max"]    = rs.max()
    if "sum" in stats:    cols["sum"]    = rs.sum()
    return pd.DataFrame(cols)
```

### `expanding_stats(s, stats=("mean",))` — acumulado

```python
def expanding_stats(s, stats=("mean",), min_periods=1):
    """Media/std móvil sin ventana fija. Útil para baseline acumulativo."""
    es = s.expanding(min_periods=min_periods)
    cols = {}
    if "mean" in stats:   cols["mean"]   = es.mean()
    if "std" in stats:    cols["std"]    = es.std()
    if "median" in stats: cols["median"] = es.median()
    if "sum" in stats:    cols["sum"]    = es.sum()
    return pd.DataFrame(cols)
```

### `lag_lead_diff(s, lags=(1,), leads=(), diffs=(1,))` — features temporales

```python
def lag_lead_diff(s, lags=(1,), leads=(), diffs=(1,)):
    """Devuelve DataFrame con columnas: lag_<k>, lead_<k>, diff_<k>, value."""
    out = {"value": s}
    for k in lags:
        out[f"lag_{k}"]   = s.shift(k)
    for k in leads:
        out[f"lead_{k}"]  = s.shift(-k)
    for k in diffs:
        out[f"diff_{k}"]  = s.diff(periods=k)
    return pd.DataFrame(out)
```

### `reindex_full_range(s, freq, fill_value=np.nan)` — rellenar huecos temporales

```python
def reindex_full_range(s, freq, fill_value=np.nan):
    """Reindexa a un rango continuo en `freq`. Marca gaps introducidos."""
    if not isinstance(s.index, pd.DatetimeIndex):
        raise ValueError("reindex_full_range requiere DatetimeIndex")
    full = pd.date_range(s.index.min(), s.index.max(), freq=freq)
    out = s.reindex(full)
    out = out.fillna(fill_value)
    # Atributo auxiliar para detectar gaps: máscara de "no estaba antes"
    out.attrs["introduced_gaps"] = int(s.index.difference(full).size == 0 and full.difference(s.index).size)
    return out
```

### `detect_periodicity(s, max_lag=None, method="acf")` — encontrar el ciclo dominante

```python
def detect_periodicity(s, max_lag=None, method="acf"):
    """Encuentra el lag con mayor autocorlación (excluyendo lag=0).

    Útil para responder '¿esta serie tiene periodicidad semanal?'.
    Devuelve dict con best_lag, autocorr, top5_lags.
    """
    s = s.dropna()
    n = len(s)
    if max_lag is None:
        max_lag = min(n // 2, 365)
    if max_lag < 2:
        return {"best_lag": None, "autocorr": None, "top_lags": {}, "note": "serie muy corta"}
    vals = s.values
    centered = vals - vals.mean()
    denom = float((centered ** 2).sum())
    if denom == 0:
        return {"best_lag": None, "autocorr": None, "top_lags": {}, "note": "serie constante"}
    acfs = {}
    for k in range(1, int(max_lag) + 1):
        acfs[k] = float((centered[:-k] * centered[k:]).sum() / denom)
    ranked = sorted(acfs.items(), key=lambda kv: kv[1], reverse=True)
    top = dict(ranked[:5])
    best_lag, best_acf = ranked[0]
    return {
        "best_lag": int(best_lag),
        "autocorr": float(best_acf),
        "top_lags": {int(k): round(v, 4) for k, v in top.items()},
        "method": method,
        "n": int(n),
        "max_lag": int(max_lag),
    }
```

### `seasonal_compare(s, period, group_freq=None, comparison="prev")` — comparar contra otro periodo

```python
def seasonal_compare(s, period, group_freq=None, comparison="prev"):
    """Compara cada punto contra el valor del periodo anterior (misma posición en el ciclo).

    period: entero, ej. 7 para semanal-diario, 12 para mensual-anual, 24 para diario-por-hora.
    group_freq: 'D'/'W'/'M'/'Q'/'Y'/'H' para alinear el índice (opcional).
    comparison: 'prev' (periodo anterior) o 'yoy' (mismo periodo, una vuelta antes).

    Devuelve DataFrame con value, comparison, delta, delta_pct.
    """
    if comparison not in ("prev", "yoy"):
        raise ValueError("comparison debe ser 'prev' o 'yoy'")
    if group_freq is not None:
        s = s.resample(group_freq).mean()
    out = pd.DataFrame({"value": s})
    if comparison == "prev":
        out["comparison"] = s.shift(period)
    else:  # yoy — se asume que la serie ya tiene group_freq aplicada
        out["comparison"] = s.shift(period)
    out["delta"]    = out["value"] - out["comparison"]
    out["delta_pct"] = (out["delta"] / out["comparison"]) * 100
    return out
```

### `naive_forecast(s, h, method="last", season=None)` — predicción naive

```python
def naive_forecast(s, h, method="last", season=None):
    """Forecast h pasos hacia adelante.

    method:
      - 'last': repite el último valor.
      - 'mean': predice la media histórica.
      - 'drift': extrapola linealmente desde el primer punto.
      - 'seasonal_last': requiere season; repite el último ciclo completo.
        p. ej. season=7 con datos diarios -> repite los últimos 7 valores.

    Devuelve DataFrame con columna 'forecast' e índice futuro.
    """
    s = s.dropna()
    if method == "last":
        forecast = np.full(h, s.iloc[-1])
    elif method == "mean":
        forecast = np.full(h, s.mean())
    elif method == "drift":
        n = len(s)
        if n < 2:
            forecast = np.full(h, s.iloc[-1])
        else:
            slope = (s.iloc[-1] - s.iloc[0]) / (n - 1)
            forecast = np.array([s.iloc[-1] + slope * (k + 1) for k in range(h)])
    elif method == "seasonal_last":
        if season is None:
            raise ValueError("method='seasonal_last' requiere season (int)")
        last_cycle = s.iloc[-season:].values
        forecast = np.tile(last_cycle, int(np.ceil(h / season)))[:h]
    else:
        raise ValueError(f"method desconocido: {method}")

    freq = pd.infer_freq(s.index) or "D"
    future_index = pd.date_range(s.index[-1], periods=h + 1, freq=freq)[1:]
    return pd.DataFrame({"forecast": forecast}, index=future_index)
```

## Snippets pre-aprobados — Tier 2 (requieren `statsmodels`)

Estos snippets se usan solo cuando los lite no alcanzan para responder la
pregunta del usuario. Documentar siempre que se importó `statsmodels` y
preferir el Tier 1 cuando haya duda.

### `seasonal_decompose(s, period, model="additive")` — descomposición clásica

```python
from statsmodels.tsa.seasonal import seasonal_decompose

def seasonal_decompose_series(s, period, model="additive"):
    """Descomposición clásica (tendencial + estacional + residual).

    model='additive' cuando la amplitud estacional es ~constante;
    'multiplicative' cuando crece con el nivel (ej. revenue, prices).
    Devuelve un objeto DecomposeResult con .observed, .trend, .seasonal, .resid.
    """
    s = s.asfreq(pd.infer_freq(s.index) or "D").interpolate("linear")
    result = seasonal_decompose(s, model=model, period=period, extrapolate_trend=0)
    return result  # .observed / .trend / .seasonal / .resid son Series
```

### `stl_decompose(s, period, robust=True)` — descomposición robusta (LOESS)

```python
from statsmodels.tsa.seasonal import STL

def stl_decompose(s, period, robust=True):
    """STL: maneja mejor outliers y cambios en la estacionalidad que la clásica."""
    s = s.asfreq(pd.infer_freq(s.index) or "D").interpolate("linear")
    stl = STL(s, period=period, robust=robust).fit()
    return stl  # .observed / .trend / .seasonal / .resid
```

### `adf_test(s, max_lags=None)` — test de estacionariedad (Augmented Dickey-Fuller)

```python
from statsmodels.tsa.stattools import adfuller

def adf_test(s, max_lags=None):
    """H0: la serie tiene una raíz unitaria (no es estacionaria).

    Devuelve dict con statistic, p_value, n_lags, n_obs, critical_values.
    Si p_value < 0.05, se rechaza H0 -> la serie es estacionaria.
    """
    s = s.dropna()
    if len(s) < 20:
        return {
            "test": "ADF",
            "statistic": None, "p_value": None,
            "n": int(len(s)),
            "effect_size": None, "effect_label": "",
            "assumptions": [],
            "note": "n<20; ADF no es confiable",
        }
    res = adfuller(s, maxlag=max_lags, autolag="AIC", result_object=False)
    stat, p, usedlag, nobs, crit, _ = res
    return {
        "test": "Augmented Dickey-Fuller",
        "statistic": float(stat),
        "p_value": float(p),
        "n": int(nobs),
        "effect_size": float(stat),
        "effect_label": "estacionaria" if p < 0.05 else "no estacionaria",
        "assumptions": ["residuos sin estructura", "lag óptimo elegido por AIC"],
        "note": f"lags usados={int(usedlag)}; crit 5%={float(crit['5%']):.3f}",
    }
```

### `acf_pacf(s, nlags=40)` — autocorrelación y autocorrelación parcial

```python
from statsmodels.tsa.stattools import acf, pacf

def acf_pacf(s, nlags=40):
    """Calcula ACF y PACF hasta nlags.

    Devuelve dict con 'acf' y 'pacf' como arrays (lag 0 a nlags).
    Útil para sugerir órdenes p, q de un ARIMA (fuera de alcance acá).
    """
    s = s.dropna()
    if len(s) < nlags + 5:
        nlags = max(1, len(s) - 5)
    return {
        "acf":  acf(s,  nlags=nlags).tolist(),
        "pacf": pacf(s, nlags=nlags).tolist(),
        "nlags": int(nlags),
        "n": int(len(s)),
    }
```

## Flujo de trabajo

1. **Confirmar** que los datos están limpios y que hay una dimensión
   temporal. Si no, volver a `pandas-cleaning`.
2. **Indexar**: aplicar `setup_datetime_index(df, time_col)` para obtener
   una `Series` con `DatetimeIndex`. Parsear fechas con `errors='coerce'`
   ya está dentro del snippet; documentar cuántos valores se descartaron.
3. **Diagnosticar la granularidad**: inspeccionar `pd.infer_freq(s.index)`
   para saber si es diaria / horaria / irregular. Si es irregular, decidir
   `freq` explícita para `resample_series`.
4. **Re-muestrear**: usar `resample_series(s, rule, agg)` para llevar la
   serie a la granularidad que matchea la pregunta del usuario ("revenue
   por mes" -> `rule='MS'`, "tickets por día" -> `rule='D'`).
5. **Suavizar / desestacionalizar visualmente** (opcional):
   `rolling_stats(s, 7)` para ver tendencia semanal sobre datos diarios.
6. **Diagnosticar estructura**:
   - Periodicidad → `detect_periodicity`.
   - Estacionariedad → `adf_test` (Tier 2).
   - Estructura de autocorrelación → `acf_pacf` (Tier 2).
   - Decomposición → `seasonal_decompose` o `stl_decompose` (Tier 2).
7. **Comparar entre periodos**: si la pregunta es del estilo "¿mejoró
   este mes respecto al anterior?", usar `seasonal_compare`.
8. **Forecast naive** (opcional): si el usuario pide predicción a corto
   plazo sin pedir un modelo, usar `naive_forecast` con uno de los 4
   métodos. Documentar que es naive y que el intervalo de confianza es 0.
9. **Visualizar**: pasar las series resultantes a `viz-patterns` —
   `rolling_stats` y descomposiciones encajan en `line facetado`;
   `naive_forecast` se sobrepone al histórico con un `line` simple.

## Lista de verificación de supuestos

| Situación | Snippet de diagnóstico | Si falla, considerar |
|---|---|---|
| Datos con frecuencia irregular | `pd.infer_freq` devuelve `None` | `resample_series` con `freq` explícita |
| Serie con muchos nulos | `s.isna().sum() / len(s)` | `reindex_full_range` + `interpolate` |
| Estacionalidad cambiante | STL vs seasonal_decompose | preferir `stl_decompose(robust=True)` |
| Serie muy corta (<2 ciclos completos) | `detect_periodicity` da lag espurio | pedir más historia o marcar como "no determinada" |
| Forecast sobre serie con tendencia fuerte | naive (last/drift) subestima | documentar el sesgo; no ajustar ARIMA acá |

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "La serie ya está en formato tiempo." | DataFrames con columna datetime string-encoded no son series temporales hasta que se setea el índice. |
| "El t-test ya mostró que difieren los meses." | Comparación entre meses sin ajustar por autocorrelación da p-values falsos; usar `seasonal_compare` primero. |
| "Resampleo a la frecuencia más fina para no perder info." | Resampleo ascendente (upsampling) sin `interpolate` mete nulos; peor, si la pregunta es mensual, upsampling confunde. |
| "El forecast es lineal, le meto una regresión." | Regresión lineal sobre el índice temporal ignora estacionalidad; usar naive como baseline mínimo antes de cualquier modelo. |
| "ADF me dijo que es estacionaria, ya está." | ADF es sensible al lag elegido; chequear siempre `n_lags` y comparar con KPSS (fuera de alcance acá). |
| "STL es siempre mejor que la clásica." | STL requiere `period >= 2` y datos sin gaps grandes; con series muy cortas la clásica puede ser más estable. |

## Señales de alerta

- `pd.infer_freq` devuelve `None` y el usuario no especifica frecuencia →
  pedir aclaración antes de resamplear.
- Serie con >30% de nulos → advertir que `interpolate` introduce sesgo;
  sugerir volver a `pandas-cleaning` para decidir la estrategia de nulos.
- `detect_periodicity` devuelve `best_lag` cercano a `n // 2` → es el
  borde, no un ciclo real; ignorar y reportar como "no determinada".
- Forecast con `h` mayor al 20% del histórico → marcar como especulativo.
- Pedido de forecasting de largo plazo (>1 año) → fuera de alcance;
  escalar a v2 (ML / forecasting dedicado).
- Serie con valores negativos donde el método multiplicative no aplica →
  cambiar a `model='additive'` en `seasonal_decompose`.

## Verificación

- [ ] La serie tiene `DatetimeIndex` antes de cualquier snippet posterior
      al `setup_datetime_index`.
- [ ] La granularidad de resampleo matchea la pregunta del usuario, no
      solo la frecuencia nativa.
- [ ] `seasonal_decompose` se llama con `period >= 2` y `model` coherente
      con la escala de los datos (aditivo vs multiplicativo).
- [ ] Los p-values y estadísticos de `adf_test` se reportan con 3-4
      decimales, nunca como "es/no es estacionaria" sin número.
- [ ] El forecast naive se etiqueta explícitamente como tal (sin
      intervalos de confianza) en la narrativa.
- [ ] Si se usó `interpolate`, se documenta cuántos puntos se rellenaron.
- [ ] Ningún snippet toma strings de expresión del usuario (sin
      `s.eval(...)` ni `pd.query(...)` con input externo).
