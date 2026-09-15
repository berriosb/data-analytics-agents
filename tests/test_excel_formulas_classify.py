"""
Unit tests para `skills/excel-formulas/recetas/classify.py`.

`classify_formula` categoriza formulas Excel (aggregate, lookup, logical,
text, date, financial, math, info) y detecta features especiales
(volatile, error, array). Es el corazon de la skill `excel-formulas`
para auditoria financiera.

Cobertura:
- Cada una de las categorias principales
- Deteccion de formulas volatiles (NOW, RAND, OFFSET, INDIRECT)
- Deteccion de errores literales (#REF!, #DIV/0!, etc.)
- Deduplicacion de funciones usadas
- Complejidad (simple / medium / complex)
- Edge cases: formula vacia, sin '=', array formula
"""

from __future__ import annotations

import pytest

from excel_formulas import recetas as ef


# -----------------------------------------------------------------------
# Categorizacion por tipo de formula
# -----------------------------------------------------------------------

class TestCategorization:

    @pytest.mark.parametrize("formula,expected_category", [
        ("=SUM(A1:A10)", "aggregate"),
        ("=AVERAGE(B1:B100)", "aggregate"),
        ("=COUNTIF(A:A, '>0')", "aggregate"),
        ("=VLOOKUP(A1, B:C, 2, FALSE)", "lookup"),
        ("=INDEX(B:B, MATCH(A1, A:A, 0))", "lookup"),
        ("=XLOOKUP(A1, B:B, C:C)", "lookup"),
        # IFERROR cae en 'lookup' cuando esta combinado con VLOOKUP porque
        # la categoria lookup se chequea ANTES que logical en classify.py
        # (lookup es mas especifica). Documentado en el orden de los elif.
        ("=IFERROR(VLOOKUP(...), 0)", "lookup"),
        ("=IF(A1 > 0, 'pos', 'neg')", "logical"),
        ("=AND(A1>0, B1<10)", "logical"),
        ("=CONCAT(A1, B1)", "text"),
        ("=LEFT(A1, 5)", "text"),
        ("=UPPER(A1)", "text"),
        ("=NOW()", "date"),
        ("=TODAY()", "date"),
        ("=YEAR(A1)", "date"),
        ("=NPV(0.1, A1:A10)", "financial"),
        ("=PMT(0.05/12, 360, -200000)", "financial"),
        ("=IRR(A1:A10)", "financial"),
        ("=ABS(A1)", "math"),
        ("=ROUND(A1, 2)", "math"),
        ("=SQRT(A1)", "math"),
        # ISBLANK/ISNUMBER caen en 'logical' (no en 'info') porque
        # el conjunto de logical se chequea ANTES que el de info en
        # classify.py, y ambos incluyen estas funciones.
        ("=ISBLANK(A1)", "logical"),
        ("=ISNUMBER(A1)", "logical"),
        # ISNONTEXT solo esta en info, asi que cae ahi correctamente.
        ("=ISNONTEXT(A1)", "info"),
    ])
    def test_categorizes_correctly(self, formula: str, expected_category: str) -> None:
        result = ef.classify_formula(formula)
        assert result["category"] == expected_category, (
            f"{formula!r} -> {result['category']!r}, esperaba {expected_category!r}"
        )

    def test_financial_takes_priority_over_aggregate(self) -> None:
        """NPV es financial, no aggregate (aunque SUM es aggregate)."""
        result = ef.classify_formula("=NPV(0.1, SUM(A1:A10))")
        assert result["category"] == "financial"

    def test_lookup_takes_priority_over_aggregate(self) -> None:
        """VLOOKUP dentro de SUM sigue siendo lookup (mas especifico)."""
        result = ef.classify_formula("=SUM(VLOOKUP(A1, B:C, 2, FALSE))")
        assert result["category"] == "lookup"


# -----------------------------------------------------------------------
# Funciones usadas: deduplicacion + case
# -----------------------------------------------------------------------

class TestFunctionsUsed:

    def test_dedupes_functions_preserving_order(self) -> None:
        """La misma funcion usada 2 veces aparece una sola vez, en orden."""
        result = ef.classify_formula("=SUM(A1) + SUM(B1) + ROUND(C1, 2)")
        assert result["functions_used"] == ["SUM", "ROUND"]

    def test_extracts_uppercase_function_names(self) -> None:
        result = ef.classify_formula("=vlookup(a1, b:c, 2, false)")
        # lowercase en el input, pero el extractor busca MAYUSCULAS via regex
        # que matchea "[A-Z][A-Z0-9_\.]+". Entonces 'vlookup' no matchea.
        # Documentamos el comportamiento: el extractor exige mayusculas.
        assert result["functions_used"] == []

    def test_uppercase_input_extracts_correctly(self) -> None:
        result = ef.classify_formula("=VLOOKUP(A1, B:C, 2, FALSE)")
        assert "VLOOKUP" in result["functions_used"]


# -----------------------------------------------------------------------
# Volatile / error / array
# -----------------------------------------------------------------------

class TestVolatileDetection:

    @pytest.mark.parametrize("formula", [
        "=NOW()",
        "=TODAY()",
        "=RAND()",
        "=RANDBETWEEN(1, 100)",
        "=OFFSET(A1, 1, 1)",
        "=INDIRECT('A' & B1)",
        "=SUM(A1) + NOW()",  # volatile mezclada con aggregate
    ])
    def test_marks_volatile(self, formula: str) -> None:
        result = ef.classify_formula(formula)
        assert result["is_volatile"] is True, f"{formula!r} deberia ser volatile"

    @pytest.mark.parametrize("formula", [
        "=SUM(A1:A10)",
        "=VLOOKUP(A1, B:C, 2, FALSE)",
        "=ROUND(A1, 2)",
    ])
    def test_non_volatile_stays_false(self, formula: str) -> None:
        result = ef.classify_formula(formula)
        assert result["is_volatile"] is False


class TestErrorDetection:

    @pytest.mark.parametrize("formula", [
        "=#REF!",
        "=#DIV/0!",
        "=#VALUE!",
        "=#NAME?",
        "=#N/A",
        "=IF(A1, 1, #REF!)",
    ])
    def test_detects_error_literal(self, formula: str) -> None:
        result = ef.classify_formula(formula)
        assert result["has_error"] is True
        # Si la formula tiene error, la categoria es 'error'
        assert result["category"] == "error"


class TestArrayFormulas:

    def test_array_formula_detected_via_braces(self) -> None:
        """Array formulas en Excel se serializan como {=FORMULA} en openpyxl."""
        result = ef.classify_formula("{=SUM(A1:A10*B1:B10)}")
        assert result["is_array"] is True

    def test_non_array_formula_not_flagged(self) -> None:
        result = ef.classify_formula("=SUM(A1:A10)")
        assert result["is_array"] is False


# -----------------------------------------------------------------------
# Complejidad
# -----------------------------------------------------------------------

class TestComplexity:

    def test_simple_for_single_function_no_nesting(self) -> None:
        result = ef.classify_formula("=SUM(A1:A10)")
        assert result["complexity"] == "simple"

    def test_medium_for_two_functions_moderate_nesting(self) -> None:
        result = ef.classify_formula("=IF(SUM(A1:A10) > 100, AVERAGE(B1:B10), 0)")
        # 2 funciones, profundidad 2
        assert result["complexity"] == "medium"

    def test_complex_for_many_functions_or_deep_nesting(self) -> None:
        result = ef.classify_formula(
            "=IF(AND(SUM(A1:A10)>100, AVERAGE(B1:B10)<50, "
            "ROUND(C1, 2)>0.5, MAX(D1:D10)<1000), 'pass', 'fail')"
        )
        # 5 funciones, profundidad 3
        assert result["complexity"] == "complex"


# -----------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_formula(self) -> None:
        result = ef.classify_formula("")
        assert result["category"] == "other"
        assert result["functions_used"] == []
        assert result["is_volatile"] is False
        assert result["complexity"] == "simple"

    def test_formula_with_leading_equals_stripped(self) -> None:
        """El '=' inicial se quita para procesar el cuerpo."""
        result_with = ef.classify_formula("=SUM(A1)")
        result_without = ef.classify_formula("SUM(A1)")
        assert result_with["functions_used"] == result_without["functions_used"]
        assert result_with["category"] == result_without["category"]

    def test_unknown_function_falls_to_other(self) -> None:
        """Una funcion que no esta en ninguna categoria queda como 'other'."""
        result = ef.classify_formula("=FOOBAR(A1)")
        assert result["category"] == "other"
        assert "FOOBAR" in result["functions_used"]
