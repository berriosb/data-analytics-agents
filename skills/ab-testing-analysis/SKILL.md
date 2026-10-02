---
name: ab-testing-analysis
description: Metodología integral y rigurosa para análisis y diseño de experimentos y tests A/B (cálculo de tamaño muestral y MDE, chequeo de Sample Ratio Mismatch / SRM con chi², cálculo de Lift con intervalos de confianza al 95%, test para conversiones binomiales y métricas continuas, y corrección de multiplicidad de Bonferroni / Benjamini-Hochberg). Úsese cuando data-explorer o reporting-analyst analicen experimentos A/B/n o el usuario evalúe el impacto causal de cambios en producto o marketing.
---

# A/B Testing Analysis

Metodología de experimentación rigurosa orientada a decisiones de producto y marketing.
Evita los errores comunes de la industria (parar el test antes de tiempo, ignorar SRM,
reportar solo p-values sin intervalos de confianza, o inflar falsos positivos con métricas múltiples).

## Descripción general

La skill cubre las 4 etapas del ciclo de experimentación:

1. **Pre-test**: Estimación de tamaño de muestra y MDE (*Minimum Detectable Effect*).
2. **Sanity check de tráfico**: Detección de *Sample Ratio Mismatch* (SRM). Si hay SRM,
   el experimento está viciado y **no** se deben interpretar las métricas.
3. **Inferencia estadística y cuantificación del impacto**:
   - Métricas de proporción/conversión (Click-Through Rate, Checkout Rate, Signup).
   - Métricas continuas (Revenue por usuario, Ticket promedio, Tiempo en app).
   - Cálculo obligatorio de **Lift relativo (%)** con **Intervalo de Confianza al 95%**.
4. **Corrección de multiplicidad**: Ajuste por comparaciones múltiples (Bonferroni / FDR)
   si se testean más de 2 variantes (A/B/C) o múltiples métricas secundarias.

Devuelve diccionarios con formato estandarizado para alimentar directamente a
`insight-synthesis`.

## Cuándo usar

- Cuando el usuario tiene datos de un experimento con grupo control y variante(s).
- Cuando el usuario pregunta:
  - "¿El cambio en el botón aumentó significativamente la conversión?"
  - "¿Cuántos usuarios necesito por variante para detectar una mejora del 5%?"
  - "¿La distribución de tráfico entre A y B fue correcta (SRM)?"
  - "¿Cuál es el Lift y su intervalo de confianza?"
- En `reporting-analyst` para sustentar recomendaciones de rollout en el brief ejecutivo.

No **usar** cuando:

- No hay grupo de control aleatorizado (series temporales pre/post sin control → usar `statistical-testing` o `time-series-patterns`).
- Los datos aún no están desglosados por variante.

## Snippets pre-aprobados (Scipy + Numpy + Statsmodels)

### 1. Pre-Test: `sample_size_estimation(baseline_cr, mde_relative, alpha=0.05, power=0.80)`

```python
import numpy as np
from scipy import stats

def sample_size_estimation(baseline_cr, mde_relative, alpha=0.05, power=0.80):
    """Calcula el tamaño de muestra requerido por variante para una métrica binaria.

    baseline_cr: tasa de conversión base (ej. 0.10 para 10%).
    mde_relative: efecto mínimo detectable relativo (ej. 0.05 para +5% de mejora relativa).
    alpha: significancia (default 5% -> z=1.96).
    power: poder estadístico (default 80% -> z=0.84).
    """
    p1 = baseline_cr
    p2 = baseline_cr * (1 + mde_relative)
    p_pooled = (p1 + p2) / 2

    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)

    # Fórmula de muestra para dos proporciones
    numerator = (z_alpha * np.sqrt(2 * p_pooled * (1 - p_pooled)) +
                 z_beta * np.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    denominator = (p2 - p1) ** 2

    n_per_variant = int(np.ceil(numerator / denominator))
    return {
        "n_per_variant": n_per_variant,
        "total_sample_size": n_per_variant * 2,
        "baseline_rate": p1,
        "target_rate": p2,
        "mde_relative_pct": mde_relative * 100.0,
        "mde_absolute_pts": (p2 - p1) * 100.0,
        "alpha": alpha,
        "power": power,
    }
```

### 2. Sanity Check: `check_srm(control_n, variant_n, expected_ratio=0.5)`

```python
def check_srm(control_n, variant_n, expected_ratio=0.5):
    """Evalúa Sample Ratio Mismatch usando Chi-Square Goodness of Fit.

    Si p_value < 0.001, hay evidencia severa de SRM (el tracking o el split falló).
    """
    total = control_n + variant_n
    expected_control = total * expected_ratio
    expected_variant = total * (1 - expected_ratio)

    observed = [control_n, variant_n]
    expected = [expected_control, expected_variant]

    chi2_stat, p_val = stats.chisquare(f_obs=observed, f_exp=expected)
    has_srm = p_val < 0.001

    return {
        "test": "Sample Ratio Mismatch (Chi²)",
        "statistic": float(chi2_stat),
        "p_value": float(p_val),
        "control_n": control_n,
        "variant_n": variant_n,
        "actual_ratio": control_n / total,
        "expected_ratio": expected_ratio,
        "has_srm": has_srm,
        "status": "FAIL (SRM Detectado - Experimento inválido)" if has_srm else "PASS (Sin SRM)",
        "note": "Alerta crítica: la asignación aleatoria falló. Revisar bots, tracking o redirecciones antes de mirar métricas." if has_srm else "",
    }
```

### 3. Test de Proporciones: `binomial_ab_test(control_conv, control_n, variant_conv, variant_n, alpha=0.05)`

```python
def binomial_ab_test(control_conv, control_n, variant_conv, variant_n, alpha=0.05):
    """Z-test para dos proporciones con Lift relativo e intervalo de confianza al (1-alpha)%.

    control_conv, variant_conv: número de éxitos/conversiones.
    """
    p_c = control_conv / control_n
    p_v = variant_conv / variant_n

    # Lift absoluto y relativo
    abs_lift = p_v - p_c
    rel_lift = (p_v - p_c) / p_c if p_c > 0 else 0.0

    # Error estándar combinado para la prueba de hipótesis
    p_pool = (control_conv + variant_conv) / (control_n + variant_n)
    se_pool = np.sqrt(p_pool * (1 - p_pool) * (1 / control_n + 1 / variant_n))
    z_score = abs_lift / se_pool if se_pool > 0 else 0.0
    p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))

    # Error estándar no combinado para el intervalo de confianza de la diferencia
    se_diff = np.sqrt((p_c * (1 - p_c) / control_n) + (p_v * (1 - p_v) / variant_n))
    z_crit = stats.norm.ppf(1 - alpha / 2)
    ci_abs_lower = abs_lift - z_crit * se_diff
    ci_abs_upper = abs_lift + z_crit * se_diff

    # Intervalo de confianza relativo aproximado (método Delta)
    ci_rel_lower = (ci_abs_lower / p_c) * 100.0 if p_c > 0 else 0.0
    ci_rel_upper = (ci_abs_upper / p_c) * 100.0 if p_c > 0 else 0.0

    is_significant = p_value < alpha

    return {
        "test": "Two-Proportion Z-Test",
        "statistic": float(z_score),
        "p_value": float(p_value),
        "control_rate_pct": p_c * 100.0,
        "variant_rate_pct": p_v * 100.0,
        "abs_lift_pts": abs_lift * 100.0,
        "rel_lift_pct": rel_lift * 100.0,
        "ci_rel_95": [float(ci_rel_lower), float(ci_rel_upper)],
        "significant": is_significant,
        "verdict": "Ganador significativo" if is_significant and rel_lift > 0 else (
            "Perdedor significativo" if is_significant and rel_lift < 0 else "Sin diferencia estadística"
        ),
        "recommendation": "Lanzar variante a producción" if is_significant and rel_lift > 0 else "Mantener control o iterar hipótesis",
    }
```

### 4. Test de Métricas Continuas: `continuous_ab_test(control_arr, variant_arr, alpha=0.05)`

```python
def continuous_ab_test(control_arr, variant_arr, alpha=0.05):
    """Welch t-test para métricas continuas (Revenue, AOV, tiempo) con Lift y CI del 95%."""
    c = np.asarray(control_arr, dtype=float)
    v = np.asarray(variant_arr, dtype=float)
    c, v = c[~np.isnan(c)], v[~np.isnan(v)]

    mean_c, mean_v = float(np.mean(c)), float(np.mean(v))
    var_c, var_v = float(np.var(c, ddof=1)), float(np.var(v, ddof=1))
    n_c, n_v = len(c), len(v)

    res = stats.ttest_ind(v, c, equal_var=False)

    abs_diff = mean_v - mean_c
    rel_diff_pct = (abs_diff / mean_c * 100.0) if mean_c != 0 else 0.0

    # Error estándar y grados de libertad Welch-Satterthwaite
    se_diff = np.sqrt(var_c / n_c + var_v / n_v)
    df_welch = (var_c / n_c + var_v / n_v)**2 / (
        (var_c / n_c)**2 / (n_c - 1) + (var_v / n_v)**2 / (n_v - 1)
    )
    t_crit = stats.t.ppf(1 - alpha / 2, df=df_welch)

    ci_abs = [float(abs_diff - t_crit * se_diff), float(abs_diff + t_crit * se_diff)]
    ci_rel = [(ci_abs[0] / mean_c * 100.0), (ci_abs[1] / mean_c * 100.0)] if mean_c != 0 else [0.0, 0.0]

    is_sig = res.pvalue < alpha

    return {
        "test": "Welch Continuous t-test",
        "statistic": float(res.statistic),
        "p_value": float(res.pvalue),
        "mean_control": mean_c,
        "mean_variant": mean_v,
        "rel_lift_pct": float(rel_diff_pct),
        "ci_rel_95": ci_rel,
        "significant": bool(is_sig),
        "verdict": "Incremento significativo" if is_sig and rel_diff_pct > 0 else (
            "Caída significativa" if is_sig and rel_diff_pct < 0 else "Neutro"
        ),
    }
```

### 5. Multiplicidad: `adjust_multiple_testing(p_values, method="fdr_bh")`

```python
def adjust_multiple_testing(p_values, method="fdr_bh"):
    """Ajusta p-values cuando se evalúan múltiples métricas secundarias o variantes.

    method: 'bonferroni' (conservador) o 'fdr_bh' (Benjamini-Hochberg, recomendado en producto).
    """
    p_arr = np.asarray(p_values, dtype=float)
    n = len(p_arr)

    if method == "bonferroni":
        adjusted = np.clip(p_arr * n, 0.0, 1.0)
    elif method == "fdr_bh":
        order = np.argsort(p_arr)
        ranks = np.empty_like(order)
        ranks[order] = np.arange(1, n + 1)
        adjusted = p_arr * n / ranks
        # Mantener monotonía
        adjusted = np.minimum.accumulate(adjusted[order[::-1]])[::-1]
        adjusted_final = np.empty_like(adjusted)
        adjusted_final[order] = np.clip(adjusted, 0.0, 1.0)
        adjusted = adjusted_final
    else:
        raise ValueError(f"Método {method} no reconocido. Usar 'bonferroni' o 'fdr_bh'.")

    return list(np.round(adjusted, 5))
```

## Señales de alerta

- **Parar el test cuando el p-value cruza 0.05 (*Peeking problem*)**: El tamaño de muestra debe respetarse antes de declarar ganador.
- **Ignorar SRM**: Si `check_srm()` detecta falla, cualquier conclusión sobre la tasa de conversión es probablemente espuria.
- **Métricas financieras con outliers severos**: Para revenue o ticket promedio, los percentiles extremos (whales) distorsionan la media; advertir y recortar al percentil 99 o usar bootstrap / log-transform.

## Verificación

- [ ] Chequeo de SRM ejecutado previamente y validado (`PASS`).
- [ ] Tamaño de muestra por grupo acorde a la potencia esperada.
- [ ] Lift relativo reportado siempre junto a su intervalo de confianza al 95%.
- [ ] Si se evalúan más de 3 métricas, ajuste por multiplicidad aplicado.
