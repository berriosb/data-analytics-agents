---
name: statistical-testing
description: Aplica tests estadísticos de uso común en EDA (t-test, Welch, Mann-Whitney, ANOVA, Kruskal-Wallis, chi², Fisher, Shapiro-Wilk, correlaciones) usando snippets pre-aprobados de scipy.stats — sin construir expresiones ad-hoc. Úsese cuando data-explorer o reporting-analyst necesiten significancia estadística sobre datos limpios: comparar una métrica entre dos o más grupos, contrastar con un valor de referencia, testear independencia en una tabla de contingencia, o reportar la fuerza de una correlación.
---

# Statistical Testing

Tests estadísticos listos para usar, envueltos en funciones pre-aprobadas con
una **forma de retorno uniforme**. Pensado para EDA y para sustentar hallazgos
en `reporting-analyst`, no para investigación inferencial formal.

## Descripción general

Cada test se invoca a través de un snippet con nombre explícito (no se
construye `scipy.stats.<algo>(...)` dinámicamente). Cada función devuelve un
`dict` con la misma forma:

```python
{
    "test":          str,    # nombre del test aplicado
    "statistic":     float,  # estadístico (t, U, F, χ², r, …)
    "p_value":       float,  # p-value de dos colas salvo que se pida una
    "n":             int,    # tamaño muestral total o por grupo
    "effect_size":   float | None,  # Cohen's d / η² / Cramér's V / |r|
    "effect_label":  str,    # "pequeño" / "mediano" / "grande" (Cohen)
    "assumptions":   list[str],  # checks que se cumplen o se violan
    "note":          str,    # advertencia si n es bajo, grupos desbalanceados, etc.
}
```

Esa forma es la que `insight-synthesis` consume después para producir el brief
de insights. Si el test no tiene un tamaño de efecto estándar (p. ej. tests
sobre una sola muestra), `effect_size` queda en `None` y `effect_label` en
`""`.

## Cuándo usar

- Después de `pandas-cleaning` en `data-explorer`, cuando una pregunta
  analítica requiera significancia estadística ("¿es la media del grupo A
  realmente distinta de la del grupo B?").
- Antes de `insight-synthesis` en `reporting-analyst`, cuando un hallazgo
  visual necesite un número de p-value para no quedar como "se ve más alto".
- En cualquier punto del flujo donde el usuario pida explícitamente un test
  ("hacé un t-test", "¿es significativa la diferencia?", "¿son independientes
  categoría y outcome?").

No **usar** cuando:

- Los datos aún no están limpios → volver a `pandas-cleaning`.
- El usuario pide modelado predictivo (regresión, clasificación supervisada)
  → fuera de alcance para v1; enrutar a `data-explorer` solo para EDA.
- El usuario pide series temporales con autocorrelación → fuera de alcance
  para esta skill; pedirle al usuario que reformule como comparación entre
  periodos (sí cubierto) o esperar a `time-series-patterns` (v2).

## Snippets pre-aprobados

Todos los snippets importan `scipy.stats` y `numpy` solo arriba del archivo,
nunca dentro del flujo del usuario. Ninguno acepta expresiones del usuario
como strings: los argumentos son siempre valores numéricos (`Series`,
`ndarray`, `list[float]`).

### `t_test_ind(a, b, equal_var=False)` — dos muestras independientes

```python
from scipy import stats
import numpy as np

def t_test_ind(a, b, equal_var=False):
    """Welch t-test por defecto (varianzas desiguales)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    res = stats.ttest_ind(a, b, equal_var=equal_var)
    # Cohen's d con pooled SD (Welch usa SD simple de cada grupo)
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    d = (a.mean() - b.mean()) / pooled if pooled > 0 else 0.0
    return {
        "test": "Welch t-test" if not equal_var else "Student t-test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(len(a) + len(b)),
        "effect_size": float(abs(d)),
        "effect_label": _cohen_label(abs(d)),
        "assumptions": ["normalidad aproximada (n>=30 por grupo) o verificar con shapiro_test"],
        "note": "" if min(len(a), len(b)) >= 30 else f"n bajo (a={len(a)}, b={len(b)}); preferir mann_whitney_u",
    }

def _cohen_label(d):
    if d < 0.2: return "insignificante"
    if d < 0.5: return "pequeño"
    if d < 0.8: return "mediano"
    return "grande"
```

### `mann_whitney_u(a, b)` — alternativa no paramétrica

```python
from scipy import stats
import numpy as np

def mann_whitney_u(a, b):
    """Test de Mann-Whitney U (no asume normalidad)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    res = stats.mannwhitneyu(a, b, alternative="two-sided")
    # r = Z / sqrt(N) — aproximado
    return {
        "test": "Mann-Whitney U",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(len(a) + len(b)),
        "effect_size": float(res.statistic / (len(a) * len(b))),
        "effect_label": "",  # sin umbral estándar
        "assumptions": ["independencia entre observaciones", "forma de la distribución similar entre grupos"],
        "note": "",
    }
```

### `anova_oneway(*groups)` — 3+ grupos, asume normalidad y homocedasticidad

```python
from scipy import stats
import numpy as np

def anova_oneway(*groups):
    """ANOVA one-way. Devuelve eta-squared como tamaño de efecto."""
    arrays = [np.asarray(g, dtype=float) for g in groups]
    arrays = [g[~np.isnan(g)] for g in arrays]
    res = stats.f_oneway(*arrays)
    # eta-squared = SS_between / SS_total
    all_vals = np.concatenate(arrays)
    grand_mean = all_vals.mean()
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in arrays)
    ss_total = ((all_vals - grand_mean) ** 2).sum()
    eta2 = ss_between / ss_total if ss_total > 0 else 0.0
    return {
        "test": "ANOVA one-way",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(sum(len(g) for g in arrays)),
        "effect_size": float(eta2),
        "effect_label": _eta_label(eta2),
        "assumptions": ["normalidad por grupo", "homocedasticidad (levene_test)"],
        "note": f"{len(arrays)} grupos; si no se cumplen supuestos, usar kruskal_wallis",
    }

def _eta_label(e):
    if e < 0.01: return "insignificante"
    if e < 0.06: return "pequeño"
    if e < 0.14: return "mediano"
    return "grande"
```

### `kruskal_wallis(*groups)` — alternativa no paramétrica a ANOVA

```python
from scipy import stats
import numpy as np

def kruskal_wallis(*groups):
    arrays = [np.asarray(g, dtype=float) for g in groups]
    arrays = [g[~np.isnan(g)] for g in arrays]
    res = stats.kruskal(*arrays)
    # epsilon-squared (H/(N-1))
    n = sum(len(g) for g in arrays)
    eps2 = (res.statistic / (n - 1)) if n > 1 else 0.0
    return {
        "test": "Kruskal-Wallis",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(n),
        "effect_size": float(eps2),
        "effect_label": _eta_label(eps2),
        "assumptions": ["independencia", "variable ordinal o continua"],
        "note": "",
    }
```

### `t_test_paired(a, b)` — antes/después sobre la misma unidad

```python
from scipy import stats
import numpy as np

def t_test_paired(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    res = stats.ttest_rel(a, b)
    diff = a - b
    d = diff.mean() / diff.std(ddof=1) if diff.std(ddof=1) > 0 else 0.0
    return {
        "test": "Paired t-test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(len(a)),
        "effect_size": float(abs(d)),
        "effect_label": _cohen_label(abs(d)),
        "assumptions": ["pareo real (mismas unidades en a y b)", "diferencias ~normales"],
        "note": "",
    }
```

### `wilcoxon(a, b)` — alternativa no paramétrica pareada

```python
from scipy import stats
import numpy as np

def wilcoxon(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    mask = ~(np.isnan(a) | np.isnan(b))
    res = stats.wilcoxon(a[mask], b[mask])
    return {
        "test": "Wilcoxon signed-rank",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(mask.sum()),
        "effect_size": None,
        "effect_label": "",
        "assumptions": ["diferencias simétricas alrededor de la mediana"],
        "note": "",
    }
```

### `t_test_1samp(a, popmean)` — contra un valor de referencia

```python
from scipy import stats
import numpy as np

def t_test_1samp(a, popmean):
    a = np.asarray(a, dtype=float)
    a = a[~np.isnan(a)]
    res = stats.ttest_1samp(a, popmean)
    d = (a.mean() - popmean) / a.std(ddof=1) if a.std(ddof=1) > 0 else 0.0
    return {
        "test": "One-sample t-test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(len(a)),
        "effect_size": float(abs(d)),
        "effect_label": _cohen_label(abs(d)),
        "assumptions": ["normalidad o n>=30"],
        "note": "",
    }
```

### `shapiro_test(a)` — chequeo de normalidad (n < 5000)

```python
from scipy import stats
import numpy as np

def shapiro_test(a):
    a = np.asarray(a, dtype=float)
    a = a[~np.isnan(a)]
    if len(a) > 5000:
        return {
            "test": "Shapiro-Wilk",
            "statistic": None,
            "p_value": None,
            "n": int(len(a)),
            "effect_size": None,
            "effect_label": "",
            "assumptions": [],
            "note": "n>5000: Shapiro no es confiable; usar dagostino_normality",
        }
    res = stats.shapiro(a)
    return {
        "test": "Shapiro-Wilk",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(len(a)),
        "effect_size": None,
        "effect_label": "",
        "assumptions": [],
        "note": "p<0.05 rechaza normalidad → preferir versión no paramétrica",
    }
```

### `dagostino_normality(a)` — alternativa para n >= 20

```python
from scipy import stats
import numpy as np

def dagostino_normality(a):
    a = np.asarray(a, dtype=float)
    a = a[~np.isnan(a)]
    res = stats.normaltest(a)
    return {
        "test": "D'Agostino-Pearson",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(len(a)),
        "effect_size": None,
        "effect_label": "",
        "assumptions": [],
        "note": "p<0.05 rechaza normalidad → preferir versión no paramétrica",
    }
```

### `levene_test(*groups)` — homocedasticidad

```python
from scipy import stats
import numpy as np

def levene_test(*groups):
    arrays = [np.asarray(g, dtype=float) for g in groups]
    arrays = [g[~np.isnan(g)] for g in arrays]
    res = stats.levene(*arrays)
    return {
        "test": "Levene",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "n": int(sum(len(g) for g in arrays)),
        "effect_size": None,
        "effect_label": "",
        "assumptions": [],
        "note": "p<0.05 rechaza homocedasticidad → usar Welch en vez de Student / Kruskal en vez de ANOVA",
    }
```

### `chi2_independence(contingency)` — tabla de contingencia

```python
from scipy import stats
import numpy as np

def chi2_independence(contingency):
    """Tabla 2D (o mayor). Devuelve Cramér's V como tamaño de efecto."""
    table = np.asarray(contingency)
    chi2, p, dof, expected = stats.chi2_contingency(table)
    n = table.sum()
    r, k = table.shape
    # Cramér's V (corrección por dimensión menor)
    v = np.sqrt(chi2 / (n * (min(r, k) - 1))) if n > 0 and min(r, k) > 1 else 0.0
    low_expected = (expected < 5).sum()
    return {
        "test": "Chi-cuadrado de independencia",
        "statistic": float(chi2),
        "p_value": float(p),
        "n": int(n),
        "effect_size": float(v),
        "effect_label": _cramers_label(v),
        "assumptions": ["frecuencias esperadas >= 5 en >=80% de celdas"],
        "note": f"{int(low_expected)} celdas con esperado<5 → considerar fisher_exact" if low_expected > 0 else "",
    }

def _cramers_label(v):
    if v < 0.1: return "insignificante"
    if v < 0.3: return "pequeño"
    if v < 0.5: return "mediano"
    return "grande"
```

### `fisher_exact(table2x2)` — alternativa para 2x2 con n bajo

```python
from scipy import stats

def fisher_exact(table2x2):
    table = np.asarray(table2x2)
    if table.shape != (2, 2):
        raise ValueError("fisher_exact espera una tabla 2x2")
    oddsratio, p = stats.fisher_exact(table)
    return {
        "test": "Fisher exact",
        "statistic": float(oddsratio),
        "p_value": float(p),
        "n": int(table.sum()),
        "effect_size": float(oddsratio),
        "effect_label": "",
        "assumptions": ["tabla 2x2 estricta"],
        "note": "oddsratio=1 indica independencia; oddsratio!=1 indica asociación",
    }
```

### `pearson_corr(x, y)` / `spearman_corr(x, y)` / `kendall_corr(x, y)`

```python
from scipy import stats
import numpy as np

def _corr(x, y, fn, name, parametric):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = ~(np.isnan(x) | np.isnan(y))
    res = fn(x[mask], y[mask])
    r = float(res.statistic)
    return {
        "test": name,
        "statistic": r,
        "p_value": float(res.pvalue),
        "n": int(mask.sum()),
        "effect_size": float(abs(r)),
        "effect_label": _cohen_label(abs(r)),
        "assumptions": ["linealidad (Pearson) / monotonía (Spearman, Kendall)"] if parametric else ["monotonía"],
        "note": "",
    }

def pearson_corr(x, y):  return _corr(x, y, stats.pearsonr, "Pearson", parametric=True)
def spearman_corr(x, y): return _corr(x, y, stats.spearmanr, "Spearman", parametric=False)
def kendall_corr(x, y):  return _corr(x, y, stats.kendalltau, "Kendall tau", parametric=False)
```

## Flujo de trabajo

1. **Confirmar** que los datos están limpios. Si no, volver a
   `pandas-cleaning`.
2. **Identificar** el tipo de pregunta:
   - ¿Comparar medias entre 2 grupos? → `t_test_ind` o `mann_whitney_u`.
   - ¿Comparar medias entre 3+ grupos? → `anova_oneway` o `kruskal_wallis`.
   - ¿Antes/después sobre las mismas unidades? → `t_test_paired` o `wilcoxon`.
   - ¿Contra un valor de referencia? → `t_test_1samp`.
   - ¿Normalidad de la distribución? → `shapiro_test` (n<5000) o
     `dagostino_normality`.
   - ¿Varianzas iguales entre grupos? → `levene_test`.
   - ¿Independencia entre dos variables categóricas? → `chi2_independence`
     o `fisher_exact`.
   - ¿Fuerza de asociación lineal/monotónica? → `pearson_corr`,
     `spearman_corr` o `kendall_corr`.
3. **Verificar supuestos** antes de elegir la versión paramétrica:
   - Normalidad: `shapiro_test` por grupo.
   - Homocedasticidad (solo ANOVA / Student): `levene_test`.
   - Si algún supuesto se viola → usar la versión no paramétrica.
4. **Aplicar** el snippet elegido. Pasar siempre `Series` (de pandas) o
   `ndarray`; los snippets manejan `NaN` internamente.
5. **Reportar** el dict resultante como una fila markdown con las columnas:
   `test | statistic | p_value | n | effect_size | label | note`.
6. **Pasar** el dict a `insight-synthesis` si el hallazgo va a generar una
   decisión.

## Lista de verificación de supuestos

| Situación | Test de supuesto | Si falla, usar |
|---|---|---|
| 2 grupos, paramétrico | `shapiro_test` por grupo | `mann_whitney_u` |
| 2 grupos, paramétrico | `levene_test` si n<30 por grupo | `t_test_ind(equal_var=False)` |
| 3+ grupos, ANOVA | `shapiro_test` por grupo | `kruskal_wallis` |
| 3+ grupos, ANOVA | `levene_test` | `kruskal_wallis` |
| Pareado | Shapiro sobre `a - b` | `wilcoxon` |
| Chi² | esperados >=5 en >=80% de celdas | `fisher_exact` (2x2) o agrupar categorías |

## Justificaciones comunes

| Justificación | Realidad |
| --- | --- |
| "Con n=500 seguro es normal." | El TLC requiere n≥30 *por grupo*, no total, y solo si la población original no es muy asimétrica. |
| "Siempre uso t-test." | El t-test asume varianzas iguales (Student) o solo normalidad (Welch); sin chequearlo se viola el supuesto. |
| "El p-value es 0.049, casi significativo." | Reportar el p-value exacto. El umbral 0.05 es arbitrario; `effect_size` + `n` importan más. |
| "ANOVA me dice cuál grupo difiere." | ANOVA es omnibus; para post-hoc (Tukey, Bonferroni) hace falta otra skill (fuera de alcance para v1). |
| "Chi² sobre cualquier tabla de contingencia." | Sin frecuencias esperadas >=5, chi² no es válido; usar Fisher o agrupar. |
| "Pearson sirve para cualquier relación." | Pearson mide solo linealidad; Spearman/Kendall cubren relaciones monotónicas no lineales. |

## Señales de alerta

- Algún grupo con `n < 5` → advertencia explícita; el test estadístico pierde
  poder, preferir bootstrap o describir sin inferencia.
- Datos con outliers extremos (|z| > 3) que no fueron tratados → nota de que
  los tests paramétricos son sensibles a outliers; reportar mediana + IQR
  además de la media.
- Comparación múltiple no corregida (varios tests sobre el mismo dataframe)
  → sugerir Bonferroni / FDR; documentar que el resultado es exploratorio.
- Pedido del usuario de "testear todo contra todo" → bloquear, pedir
  hipótesis específicas.
- Variable categórica con >20 niveles → chi² puede dar associações
  espurias; sugerir agrupar o reducir dimensionalidad.

## Verificación

- [ ] Los datos pasaron por `pandas-cleaning` (sin nulos sin normalizar,
      dtypes consistentes).
- [ ] El test elegido matchea la pregunta (2 grupos vs 3+, pareado vs
      independiente, etc.).
- [ ] Los supuestos se chequearon explícitamente cuando aplica (normalidad
      + homocedasticidad para tests paramétricos).
- [ ] El snippet usado es uno de los listados arriba, no una llamada
      ad-hoc a `scipy.stats`.
- [ ] El reporte incluye `test`, `statistic`, `p_value`, `n` y
      `effect_size` (o `None` explícito si no aplica).
- [ ] El p-value se reporta con 3-4 decimales, nunca como "p<0.05" sin
      número.
- [ ] Si se hicieron tests múltiples sobre el mismo dataframe, se documentó
      la falta de corrección (o se aplicó Bonferroni/FDR).
