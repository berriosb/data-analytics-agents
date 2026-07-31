---
name: pandas-cleaning
description: Limpia un dataset tabular perfilado usando solo snippets pre-aprobados de pandas (sin eval). Úsese cuando el usuario aprobó un plan de limpieza de csv-profiler. Cubre manejo de nulos, deduplicación, coerción de dtype, normalización y eliminación de columnas.
---

# Pandas Cleaning

Lectura-modificación-escritura. **Opera siempre sobre una ruta de salida
nombrada por el usuario**. Nunca sobrescribe la entrada. Usa solo los snippets
pre-aprobados listados abajo — nunca escribe expresiones de pandas abiertas
que el agente componga en tiempo de ejecución.

## Descripción general

Cada operación de abajo es un snippet con nombre, con entrada y salida
claramente tipadas. El agente elige un snippet, completa los parámetros, lo
corre y muestra un diff contra la entrada. Componer snippets está permitido;
escribir pandas arbitrario no.

## Cuándo usar

- Después de que `csv-profiler` haya producido el perfil.
- Después de que el usuario haya aprobado un plan de limpieza escrito.
- Cuando el usuario pide "limpiá este dataset en `<output_path>`".

No **usar** cuando:

- El perfil no fue compartido con el usuario.
- El usuario no nombró una ruta de salida.
- El usuario quiere "simplemente descartar las filas malas" sin justificación.

## Snippets pre-aprobados

### `load_input(path)` — carga un archivo a un DataFrame

```python
import pandas as pd
import numpy as np

def load_input(path):
    ext = path.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        return pd.read_csv(path)
    if ext in ("parquet", "pq"):
        return pd.read_parquet(path)
    if ext in ("xlsx", "xls"):
        return pd.read_excel(path)
    raise ValueError(f"Unsupported extension: {ext}")
```

### `normalize_nulls(df)` — convierte tokens de string nulos a NaN

```python
NULL_TOKENS = ["", "nan", "NaN", "NAN", "null", "NULL", "None", "none", "?"]
def normalize_nulls(df):
    df = df.replace(NULL_TOKENS, np.nan)
    df = df.replace([np.inf, -np.inf], np.nan)
    return df
```

### `drop_duplicates(df, subset=None)` — elimina filas duplicadas

```python
def drop_duplicates(df, subset=None):
    return df.drop_duplicates(subset=subset).reset_index(drop=True)
```

### `coerce_numeric(df, columns)` — fuerza columnas listadas a numéricas

```python
def coerce_numeric(df, columns):
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
```

### `coerce_datetime(df, columns, fmt=None)` — fuerza columnas listadas a datetime

```python
def coerce_datetime(df, columns, fmt=None):
    for c in columns:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], format=fmt, errors="coerce")
    return df
```

### `drop_columns(df, columns)` — elimina columnas listadas

```python
def drop_columns(df, columns):
    existing = [c for c in columns if c in df.columns]
    return df.drop(columns=existing)
```

### `drop_na_rows(df, subset=None, how="any")` — elimina filas con NA en subset

```python
def drop_na_rows(df, subset=None, how="any"):
    return df.dropna(subset=subset, how=how).reset_index(drop=True)
```

### `fill_na(df, columns, value)` — rellena NA en columnas listadas con value

```python
def fill_na(df, columns, value):
    for c in columns:
        if c in df.columns:
            df[c] = df[c].fillna(value)
    return df
```

### `strip_string_columns(df, columns)` — quita espacios en columnas string

```python
def strip_string_columns(df, columns):
    for c in columns:
        if c in df.columns and df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan})
    return df
```

### `lowercase_string_columns(df, columns)` — pasa a minúsculas columnas string

```python
def lowercase_string_columns(df, columns):
    for c in columns:
        if c in df.columns and df[c].dtype == object:
            df[c] = df[c].astype(str).str.lower()
    return df
```

### `save_output(df, path)` — escribe el DataFrame limpio

```python
def save_output(df, path):
    ext = path.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        df.to_csv(path, index=False)
    elif ext in ("parquet", "pq"):
        df.to_parquet(path, index=False)
    elif ext in ("xlsx", "xls"):
        df.to_excel(path, index=False)
    else:
        raise ValueError(f"Unsupported extension: {ext}")
```

## Flujo de trabajo

1. **Confirmar**: el perfil existe, el usuario aprobó el plan, la ruta de
   salida está fijada.
2. **Cargar**: `load_input(input_path)` → `df`.
3. **Normalizar**: `normalize_nulls(df)`.
4. **Aplicar** los snippets aprobados en el orden que el usuario pidió. Cada
   llamada devuelve un nuevo DataFrame — no mutar in situ.
5. **Guardar**: `save_output(df, output_path)`.
6. **Re-perfilar**: re-correr `csv-profiler/SKILL.md` sobre la salida.
   Producir un diff contra la original.
7. **Reportar**: escribir un resumen de "qué cambió" — filas agregadas, filas
   eliminadas, columnas descartadas, NA rellenados, duplicados eliminados,
   dtypes forzados.

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "Es una sola línea, lo escribo inline." | Las expresiones inline de pandas son cómo pasan los sobreescritos silenciosos. |
| "Uso `df.query(user_expr)`." | Las expresiones del usuario en `query` son un vector de inyección de código. |
| "Hago `eval` de la expresión pandas del usuario." | Nunca. Usar los snippets de arriba. |
| "Sobreescribir la entrada está bien, el usuario lo dijo." | Aun así, hacer snapshot a `<input>.bak` primero. |

## Señales de alerta

- El usuario quiere descartar >50% de las filas — bloquear, preguntar por qué.
- El usuario quiere sobreescribir el archivo de entrada — hacer snapshot
  primero.
- El plan incluye un `drop_column` para cualquier columna que pueda ser un ID
  único — marcar y confirmar.
- La ruta de salida coincide con la ruta de entrada — rechazar.
- El plan incluye rellenar nulos con 0 (o cualquier constante) en una
  columna numérica sin nombrar la columna — preguntar.

## Verificación

- [ ] El archivo de entrada no cambió (tamaño, mtime, hash).
- [ ] El archivo de salida existe en la ruta nombrada por el usuario.
- [ ] El diff del re-perfil muestra los cambios que se aplicaron.
- [ ] Cada snippet aplicado es uno de los snippets pre-aprobados de arriba.
- [ ] No hay `eval`, no hay `exec`, no hay `df.query(<expresión del usuario>)`.
