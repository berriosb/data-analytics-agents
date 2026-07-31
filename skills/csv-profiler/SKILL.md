---
name: csv-profiler
description: Produce un perfil estructural de solo lectura de un archivo CSV / Parquet / Excel (forma, dtypes, nulos, duplicados, distribuciones, outliers). Úsese al primer encuentro con un archivo tabular, antes de limpiarlo, o como primer paso de cualquier tarea de data-explorer.
---

# CSV Profiler

Solo lectura. Produce un reporte en markdown. Nunca modifica el archivo de
origen.

## Descripción general

Genera un perfil estructural de un archivo tabular usando `pandas` (para
CSV/Excel) o `pyarrow` (para Parquet). La salida es markdown para que el
usuario pueda revisar antes de tomar cualquier decisión de limpieza.

## Cuándo usar

- Primer encuentro con un nuevo archivo tabular (cualquier tamaño hasta ~2M
  filas).
- Antes de cargar la skill `pandas-cleaning`.
- Cuando el usuario pregunta "¿qué tiene este archivo?".
- Como paso de re-perfilado después de una limpieza, para producir un diff.

No **usar** cuando:

- El usuario quiere que el archivo se analice semánticamente →
  `pandas-cleaning` después de esta skill.
- Los datos están en una base SQL → agente `sql-analyst`.
- El archivo no es tabular (imagen, PDF, JSON tree) → fuera de alcance para v1.

## Flujo de trabajo

### 1. Detectar y cargar

```python
import pandas as pd
import numpy as np

path = "<input_path>"
ext = path.rsplit(".", 1)[-1].lower()

if ext == "csv":
    df = pd.read_csv(path)
elif ext in ("parquet", "pq"):
    df = pd.read_parquet(path)
elif ext in ("xlsx", "xls"):
    df = pd.read_excel(path)
else:
    raise ValueError(f"Unsupported extension: {ext}")
```

Limitar los warnings para archivos muy grandes. Si `len(df) > 2_000_000`,
advertir al usuario y recomendar un paso de muestreo previo.

### 2. Normalizar antes de medir

Tratar estos tokens de string como nulos para que el conteo de nulos no
quede subestimado:

```python
NULL_TOKENS = {"", "nan", "NaN", "NAN", "null", "NULL", "None", "none", "?"}
df = df.replace(NULL_TOKENS, np.nan)
df = df.replace([np.inf, -np.inf], np.nan)
```

Después medir los nulos con `df.isna().sum()` — este es el único conteo de
nulos correcto.

### 3. Perfil por columna

```python
profile_rows = []
for col in df.columns:
    s = df[col]
    row = {
        "columna": col,
        "dtype": str(s.dtype),
        "n_nulos": int(s.isna().sum()),
        "pct_nulos": round(s.isna().mean() * 100, 2),
        "n_unicos": int(s.nunique(dropna=True)),
    }
    if pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s):
        non_null = s.dropna()
        if len(non_null):
            q1, q3 = non_null.quantile(0.25), non_null.quantile(0.75)
            iqr = q3 - q1
            outliers = int(((non_null < q1 - 1.5 * iqr) | (non_null > q3 + 1.5 * iqr)).sum())
            row.update({
                "min": float(non_null.min()),
                "max": float(non_null.max()),
                "media": round(float(non_null.mean()), 4),
                "mediana": float(non_null.median()),
                "std": round(float(non_null.std()), 4),
                "outliers_iqr": outliers,
            })
    elif pd.api.types.is_datetime64_any_dtype(s):
        row["min"] = str(s.min())
        row["max"] = str(s.max())
    else:
        # categórico / object
        top = s.value_counts(dropna=True).head(5)
        row["top5"] = "; ".join(f"{v!r}:{n}" for v, n in top.items())
    profile_rows.append(row)

profile_df = pd.DataFrame(profile_rows)
```

### 4. Hechos de toda la tabla

- `len(df)` filas × `df.shape[1]` columnas
- `int(df.duplicated().sum())` duplicados
- `int(df.memory_usage(deep=True).sum() / 1024 / 1024)` MB
- ¿nombres de columna duplicados? `df.columns.duplicated().any()`

### 5. Salida como markdown

Escribir el perfil en `<input_basename>_profile.md`. Usar la tabla por columna
del paso 3 más los hechos de toda la tabla del paso 4.

```python
with open(out_path, "w") as f:
    f.write(profile_df.to_markdown(index=False))
    f.write("\n\n## Tabla completa\n\n")
    f.write(f"- filas: {len(df)}\n")
    f.write(f"- columnas: {df.shape[1]}\n")
    f.write(f"- duplicados: {df.duplicated().sum()}\n")
    f.write(f"- memoria: {df.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB\n")
```

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "Son solo 200 filas, lo miro a ojo." | Mirar a ojo se pierde nulos del 5% en la columna del medio. |
| "Podemos saltarnos la normalización de nulos." | Sin ella, `''`, `'nan'`, `'null'` cuentan como valores distintos. |
| "Simplemente imprimir `df.describe()`." | `describe` se saltea las columnas object y no muestra nada sobre nulos. |
| "Vamos a perfilar después de limpiar." | El perfil pre-limpieza es el único que documenta la entrada. |

## Señales de alerta

- Más del 30% de nulos en cualquier columna que el usuario nombró como
  "clave" o "target".
- Dtypes mezclados en la misma columna (números almacenados como strings,
  etc.).
- Columnas de fecha almacenadas como object.
- Columnas de ID con duplicados (≥2% de las filas).
- Memoria > 1 GB — sugerir muestreo o procesamiento por chunks antes de
  limpiar.

## Verificación

- [ ] Los tokens de nulos fueron normalizados antes de medir.
- [ ] El markdown de salida lista **todas** las columnas (no solo las
  numéricas).
- [ ] Para columnas numéricas: min, max, media, mediana, std y conteo de
  outliers presentes.
- [ ] Para columnas no numéricas: top-5 valores presentes.
- [ ] La sección de tabla completa lista filas, columnas, duplicados, memoria.
- [ ] El archivo de origen **no** fue modificado.
