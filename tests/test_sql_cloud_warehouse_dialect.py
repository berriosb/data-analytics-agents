"""
Unit tests para `skills/sql-cloud-warehouse/recetas/dialect_snippets.py`.

Estos snippets resuelven el gap mas concreto del toolkit: cuando se
escribe una query para Snowflake vs BigQuery vs Redshift vs Databricks,
las diferencias de sintaxis (DATE_TRUNC con args en orden distinto,
IFF vs IF vs CASE, SAFE_CAST vs TRY_CAST) rompen la query si se mezclan.

Cobertura:
- Cada dialecto devuelve la sintaxis correcta
- `dialect_for` rechaza warehouses no soportados
- Edge cases: limit <= 0, args en mayusculas/minusculas
"""

from __future__ import annotations

import pytest

from sql_cloud_warehouse import recetas as scw


# -----------------------------------------------------------------------
# DATE_TRUNC — el caso mas confuso (BigQuery invierte los args)
# -----------------------------------------------------------------------

class TestDateTrunc:

    def test_snowflake_uses_string_literal_first(self) -> None:
        """Snowflake: DATE_TRUNC('month', col) — string como primer arg."""
        result = scw.date_trunc("month", "col", "snowflake")
        assert result == "DATE_TRUNC('month', col)"

    def test_bigquery_uses_unquoted_keyword_second(self) -> None:
        """BigQuery: DATE_TRUNC(col, MONTH) — keyword sin comillas como 2do arg."""
        result = scw.date_trunc("month", "col", "bigquery")
        assert result == "DATE_TRUNC(col, MONTH)"

    def test_redshift_uses_string_literal_first(self) -> None:
        """Redshift: DATE_TRUNC('month', col) — mismo formato que Snowflake."""
        result = scw.date_trunc("month", "col", "redshift")
        assert result == "DATE_TRUNC('month', col)"

    def test_databricks_uses_string_literal_first(self) -> None:
        """Databricks (Spark SQL): DATE_TRUNC('month', col) — mismo que Snowflake."""
        result = scw.date_trunc("month", "col", "databricks")
        assert result == "DATE_TRUNC('month', col)"

    def test_bigquery_uppercases_the_part_keyword(self) -> None:
        """El 'part' se normaliza a mayusculas para BigQuery (MONTH vs month)."""
        result = scw.date_trunc("day", "ts", "bigquery")
        assert result == "DATE_TRUNC(ts, DAY)"

    def test_snowflake_lowercases_the_part_string(self) -> None:
        """El string para Snowflake va en lowercase (convention)."""
        result = scw.date_trunc("YEAR", "ts", "snowflake")
        assert result == "DATE_TRUNC('year', ts)"

    def test_unsupported_warehouse_raises(self) -> None:
        """Un warehouse desconocido dispara error explicito."""
        with pytest.raises(ValueError) as exc:
            scw.date_trunc("month", "col", "oracle")
        assert "oracle" in str(exc.value).lower()
        assert "no soportado" in str(exc.value).lower()


# -----------------------------------------------------------------------
# CURRENT_TIMESTAMP — Redshift usa GETDATE(), los demas no
# -----------------------------------------------------------------------

class TestCurrentTimestamp:

    @pytest.mark.parametrize("warehouse,expected", [
        ("snowflake", "CURRENT_TIMESTAMP()"),
        ("bigquery", "CURRENT_TIMESTAMP()"),
        ("databricks", "CURRENT_TIMESTAMP()"),
        ("redshift", "GETDATE()"),
    ])
    def test_returns_correct_function(self, warehouse: str, expected: str) -> None:
        assert scw.current_timestamp(warehouse) == expected


# -----------------------------------------------------------------------
# SAFE_CAST / TRY_CAST
# -----------------------------------------------------------------------

class TestSafeCast:

    def test_bigquery_uses_safe_cast(self) -> None:
        """BigQuery: SAFE_CAST(expr AS type)."""
        result = scw.safe_cast("amount", "FLOAT64", "bigquery")
        assert result == "SAFE_CAST(amount AS FLOAT64)"

    @pytest.mark.parametrize("warehouse", ["snowflake", "redshift", "databricks"])
    def test_others_use_try_cast(self, warehouse: str) -> None:
        """Snowflake / Redshift / Databricks: TRY_CAST."""
        result = scw.safe_cast("amount", "FLOAT", warehouse)
        assert result == "TRY_CAST(amount AS FLOAT)"


# -----------------------------------------------------------------------
# Conditional — IFF / IF / CASE WHEN
# -----------------------------------------------------------------------

class TestConditional:

    def test_snowflake_uses_iff(self) -> None:
        result = scw.conditional("x > 0", "1", "0", "snowflake")
        assert result == "IFF(x > 0, 1, 0)"

    @pytest.mark.parametrize("warehouse", ["bigquery", "databricks"])
    def test_bigquery_and_databricks_use_if(self, warehouse: str) -> None:
        result = scw.conditional("x > 0", "1", "0", warehouse)
        assert result == "IF(x > 0, 1, 0)"

    def test_redshift_uses_case_when(self) -> None:
        """Redshift no tiene IFF ni IF nativo — usa CASE WHEN."""
        result = scw.conditional("x > 0", "1", "0", "redshift")
        assert result == "CASE WHEN x > 0 THEN 1 ELSE 0 END"


# -----------------------------------------------------------------------
# TOP / LIMIT
# -----------------------------------------------------------------------

class TestTopN:

    @pytest.mark.parametrize("warehouse", ["snowflake", "bigquery", "redshift", "databricks"])
    def test_all_use_limit_n(self, warehouse: str) -> None:
        assert scw.top_n(10, warehouse) == "LIMIT 10"

    def test_rejects_non_positive_limit(self) -> None:
        with pytest.raises(ValueError) as exc:
            scw.top_n(0, "snowflake")
        assert "limit" in str(exc.value).lower()

    def test_rejects_negative_limit(self) -> None:
        with pytest.raises(ValueError):
            scw.top_n(-5, "snowflake")

    def test_casts_to_int(self) -> None:
        """Aunque se pase float, se serializa como int."""
        assert scw.top_n(10.5, "snowflake") == "LIMIT 10"


# -----------------------------------------------------------------------
# dialect_for — el normalizador central
# -----------------------------------------------------------------------

class TestDialectFor:

    @pytest.mark.parametrize("warehouse", ["snowflake", "bigquery", "redshift", "databricks"])
    def test_lowercases_input(self, warehouse: str) -> None:
        assert scw.dialect_for(warehouse.upper()) == warehouse

    def test_unsupported_raises(self) -> None:
        with pytest.raises(ValueError):
            scw.dialect_for("postgres")

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            scw.dialect_for("")


# -----------------------------------------------------------------------
# identifier_quote — backticks vs comillas dobles segun dialecto
# -----------------------------------------------------------------------

class TestIdentifierQuote:

    @pytest.mark.parametrize("warehouse", ["snowflake", "redshift"])
    def test_uses_double_quotes_for_ansi_dialects(self, warehouse: str) -> None:
        """Snowflake y Redshift usan comillas dobles (ANSI SQL)."""
        assert scw.identifier_quote("customer_id", warehouse) == '"customer_id"'

    @pytest.mark.parametrize("warehouse", ["bigquery", "databricks"])
    def test_uses_backticks_for_mysql_style_dialects(self, warehouse: str) -> None:
        """BigQuery y Databricks usan backticks (estilo MySQL/Spark)."""
        assert scw.identifier_quote("customer_id", warehouse) == "`customer_id`"

    def test_preserves_special_chars_in_name(self) -> None:
        """Nombres con guion, espacio o punto se entrecomillan tal cual.

        El escape interno NO se hace aca — es responsabilidad del caller.
        """
        assert scw.identifier_quote("my-table", "bigquery") == "`my-table`"
        assert scw.identifier_quote("my table", "snowflake") == '"my table"'
        assert scw.identifier_quote("schema.table", "databricks") == "`schema.table`"

    def test_unsupported_warehouse_raises(self) -> None:
        """Mismo comportamiento que el resto: warehouse desconocido falla explicito."""
        with pytest.raises(ValueError) as exc:
            scw.identifier_quote("foo", "oracle")
        assert "oracle" in str(exc.value).lower()


# -----------------------------------------------------------------------
# qualify_clause — filtrar window functions
# -----------------------------------------------------------------------

class TestQualifyClause:

    @pytest.mark.parametrize("warehouse", ["databricks", "snowflake"])
    def test_emits_qualify_for_native_dialects(self, warehouse: str) -> None:
        """Databricks (Spark SQL 3.2+) y Snowflake (2023+) soportan QUALIFY nativo."""
        assert scw.qualify_clause("rn = 1", warehouse) == "QUALIFY rn = 1"

    def test_supports_complex_condition(self) -> None:
        """La condicion puede incluir cualquier predicado, no solo igualdad."""
        result = scw.qualify_clause("rn <= 5 AND amount > 100", "databricks")
        assert result == "QUALIFY rn <= 5 AND amount > 100"

    @pytest.mark.parametrize("warehouse", ["bigquery", "redshift"])
    def test_raises_for_unsupported_dialects(self, warehouse: str) -> None:
        """BigQuery y Redshift NO soportan QUALIFY — caller debe reescribir."""
        with pytest.raises(scw.UnsupportedQualifyError) as exc:
            scw.qualify_clause("rn = 1", warehouse)
        assert warehouse in str(exc.value)
        # El mensaje debe incluir la receta de reescritura (subquery)
        assert "subquery" in str(exc.value).lower()

    def test_unsupported_error_warehouse_attribute(self) -> None:
        """El error expone el warehouse como atributo (no solo en el mensaje)."""
        try:
            scw.qualify_clause("rn = 1", "bigquery")
        except scw.UnsupportedQualifyError as e:
            assert e.warehouse == "bigquery"
        else:
            pytest.fail("Deberia haber levantado UnsupportedQualifyError")
