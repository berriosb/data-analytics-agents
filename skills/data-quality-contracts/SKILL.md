---
name: data-quality-contracts
description: Validación declarativa de calidad de datos y contratos de esquemas sobre datasets tabulares (Pandas / DuckDB): aserciones de no-nulidad, unicidad de llaves primarias, rangos numéricos válidos, dominios de valores permitidos (enums), regex patterns y consistencia lógica entre columnas. Genera un reporte estructurado de conformidad (PASS/FAIL) con conteo de violaciones y ejemplos. Úsese antes de exportar datos, alimentar dashboards o entrenar modelos.
---

# Data Quality Contracts

Especializada en la verificación formal de **contratos de datos y reglas de integridad**
sobre datasets procesados. Adopta las mejores prácticas de *Analytics Engineering*
(dbt tests, Great Expectations) sin requerir infraestructura externa: validaciones
declarativas, puras y reproducibles sobre DataFrames.

## Descripción general

La limpieza ad-hoc (`pandas-cleaning`) transforma columnas, pero un contrato de calidad
asegura formalmente que los datos transformados **cumplen las expectativas del negocio**
antes de guardarlos a disco o alimentar modelos/reportes.

Provee:
1. **Reglas declarativas pre-aprobadas**:
   - `is_unique`: verificación de llaves primarias o IDs.
   - `is_not_null`: completitud en columnas obligatorias.
   - `in_range`: acotación de valores (`min <= x <= max`).
   - `is_in_set`: pertenencia a listas válidas de categorías (`status IN (...)`).
   - `matches_regex`: formato estándar (emails, RUTs/IDs, códigos postales).
   - `custom_condition`: aserciones multivariadas (ej. `fecha_entrega >= fecha_pedido`).
2. **Reporte estructurado de calidad**: tabla de resultados (PASS / FAIL, % de violación,
   filas afectadas y ejemplos de valores inválidos).

## Cuándo usar

- Al finalizar la limpieza en `data-explorer`, antes de entregar el archivo.
- Antes de que `sql-analyst` ejecute inserciones o persistencia con `sql-write`.
- Antes de que `ml-modeler` inicie el split y entrenamiento de features.
- Cuando el usuario pide "validá si los datos cumplen las reglas de negocio".

No **usar** cuando:

- El dataset está crudo y todavía no se hizo el perfil inicial (`csv-profiler` primero).
- No hay reglas o expectativas de negocio definidas (pedir las reglas primero).

## Snippet pre-aprobado (Pandas)

```python
import pandas as pd
import numpy as np

def validate_data_contract(df, rules, raise_on_fail=False):
    """Ejecuta una lista declarativa de reglas de calidad sobre un DataFrame.

    rules: lista de dicts con la especificación de cada test.
      Ejemplos de regla:
      - {"type": "is_unique", "column": "id"}
      - {"type": "is_not_null", "column": "email"}
      - {"type": "in_range", "column": "age", "min": 0, "max": 120}
      - {"type": "is_in_set", "column": "status", "values": ["ACTIVE", "CHURNED"]}
      - {"type": "matches_regex", "column": "zip_code", "pattern": r"^\d{5}$"}
      - {"type": "custom_condition", "description": "fin >= inicio", "fn": lambda d: d["end_date"] >= d["start_date"]}

    Devuelve dict con reporte estructurado y estado global.
    """
    total_rows = len(df)
    results = []
    any_failed = False

    for rule in rules:
        r_type = rule.get("type")
        col = rule.get("column")
        desc = rule.get("description", f"{r_type} sobre '{col}'")

        failed_mask = pd.Series(False, index=df.index)

        if r_type == "is_unique":
            failed_mask = df.duplicated(subset=[col], keep=False)
        elif r_type == "is_not_null":
            failed_mask = df[col].isna() | df[col].isin(["", "nan", "NaN", "null", "NULL"])
        elif r_type == "in_range":
            min_v = rule.get("min", -np.inf)
            max_v = rule.get("max", np.inf)
            val_num = pd.to_numeric(df[col], errors="coerce")
            failed_mask = (val_num < min_v) | (val_num > max_v) | val_num.isna()
        elif r_type == "is_in_set":
            allowed = set(rule.get("values", []))
            failed_mask = ~df[col].isin(allowed)
        elif r_type == "matches_regex":
            pat = rule.get("pattern", "")
            failed_mask = ~df[col].astype(str).str.match(pat, na=False)
        elif r_type == "custom_condition":
            condition_series = rule["fn"](df)
            failed_mask = ~condition_series
        else:
            raise ValueError(f"Tipo de regla desconocido: {r_type}")

        failed_count = int(failed_mask.sum())
        failed_pct = round(failed_count / total_rows * 100.0, 2) if total_rows > 0 else 0.0
        passed = failed_count == 0

        if not passed:
            any_failed = True
            examples = df.loc[failed_mask, col].dropna().head(3).tolist() if col and col in df.columns else []
        else:
            examples = []

        results.append({
            "rule": desc,
            "status": "PASS" if passed else "FAIL",
            "failed_count": failed_count,
            "failed_pct": failed_pct,
            "sample_errors": examples,
        })

    report_df = pd.DataFrame(results)

    if raise_on_fail and any_failed:
        failed_rules = report_df[report_df["status"] == "FAIL"]["rule"].tolist()
        raise ValueError(f"Contrato de datos violado en {len(failed_rules)} regla(s): {', '.join(failed_rules)}")

    return {
        "global_status": "FAIL" if any_failed else "PASS",
        "total_records": total_rows,
        "total_rules": len(rules),
        "passed_rules": int((report_df["status"] == "PASS").sum()),
        "failed_rules": int((report_df["status"] == "FAIL").sum()),
        "report": report_df,
    }
```

### Formato de salida y reporte Markdown

Cuando el agente ejecute el contrato, debe imprimir la tabla resumen:

| Regla | Estado | Filas Fallidas | % Afectado | Ejemplos de Error |
|---|:---:|:---:|:---:|---|
| `is_unique` sobre 'order_id' | **PASS** | 0 | 0.0% | — |
| `is_not_null` sobre 'user_id' | **PASS** | 0 | 0.0% | — |
| `in_range` (0-1000000) sobre 'monto' | **FAIL** | 3 | 0.03% | [-50.0, -12.5] |
| `is_in_set` sobre 'status' | **PASS** | 0 | 0.0% | — |

## Señales de alerta

- **Contrato con 100% PASS pero sin reglas de unicidad**: Las llaves duplicadas son la causa #1 de métricas infladas en joins posteriores.
- **Validar rangos numéricos sobre strings**: Asegurar que las columnas fueron coaccionadas con `coerce_numeric` antes de chequear rangos.
- **Sobreescribir datos ante un FAIL**: Si el contrato falla, bloquear el pipeline y notificar al usuario en lugar de guardar silenciosamente.

## Verificación

- [ ] Todas las columnas clave (`primary_key`, `foreign_key`) tienen reglas explícitas.
- [ ] Ninguna regla falla con errores de tipo de dato no controlado.
- [ ] El veredicto global es reportado al usuario antes de persistir la tabla o generar gráficos.
