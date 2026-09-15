"""
Snippets SQL por dialecto. Funciones puras (sin DB connection) que devuelven
strings SQL listos para interpolar en una query.

Las 3 reglas de oro:
1. Snowflake usa comillas simples y `IFF(cond, a, b)` (estilo IF).
2. BigQuery usa backticks para identificadores y `SAFE_CAST` para type cast.
3. Redshift usa `CASE WHEN` (estilo Postgres) y `GETDATE()` para current.

Estos snippets existen para que el agente NO mezcle sintaxis entre
warehouses cuando arme queries (que era el gap real del toolkit).
"""

from __future__ import annotations


DIALECTS = ("snowflake", "bigquery", "redshift", "databricks")


def dialect_for(warehouse_type: str) -> str:
    """Normaliza el warehouse_type a uno de los dialectos soportados."""
    wh = (warehouse_type or "").lower()
    if wh not in DIALECTS:
        raise ValueError(
            f"dialect_for: warehouse '{warehouse_type}' no soportado. "
            f"Use uno de {DIALECTS}."
        )
    return wh


# ---- Date / time ------------------------------------------------------------

def date_trunc(part: str, column: str, warehouse_type: str) -> str:
    """Trunca una columna de fecha a la parte pedida (month/day/year/hour).

    Snowflake:   DATE_TRUNC('month', col)
    BigQuery:    DATE_TRUNC(col, MONTH)
    Redshift:    DATE_TRUNC('month', col)
    Databricks:  DATE_TRUNC('month', col)
    """
    wh = dialect_for(warehouse_type)
    if wh == "bigquery":
        # BigQuery usa MONTH/DAY/YEAR/HOUR sin comillas
        return f"DATE_TRUNC({column}, {part.upper()})"
    # Snowflake, Redshift y Databricks usan la misma firma con string literal
    return f"DATE_TRUNC('{part.lower()}', {column})"


def current_timestamp(warehouse_type: str) -> str:
    """Devuelve la expresion para "timestamp actual" del dialecto."""
    wh = dialect_for(warehouse_type)
    if wh == "redshift":
        return "GETDATE()"
    return "CURRENT_TIMESTAMP()"  # Snowflake, BigQuery, Databricks


# ---- Type cast --------------------------------------------------------------

def safe_cast(expression: str, target_type: str, warehouse_type: str) -> str:
    """Type-cast seguro (devuelve NULL en caso de error).

    BigQuery: SAFE_CAST(expr AS target)
    Snowflake/Redshift/Databricks: TRY_CAST(expr AS target)
    """
    wh = dialect_for(warehouse_type)
    if wh == "bigquery":
        return f"SAFE_CAST({expression} AS {target_type})"
    return f"TRY_CAST({expression} AS {target_type})"


# ---- Conditional ------------------------------------------------------------

def conditional(condition: str, when_true: str, when_false: str,
                warehouse_type: str) -> str:
    """Funcion condicional ternaria.

    Snowflake:             IFF(cond, a, b)
    BigQuery/Databricks:   IF(cond, a, b)
    Redshift:              CASE WHEN cond THEN a ELSE b END
    """
    wh = dialect_for(warehouse_type)
    if wh == "snowflake":
        return f"IFF({condition}, {when_true}, {when_false})"
    if wh in ("bigquery", "databricks"):
        return f"IF({condition}, {when_true}, {when_false})"
    return f"CASE WHEN {condition} THEN {when_true} ELSE {when_false} END"


# ---- Top N ------------------------------------------------------------------

def top_n(limit: int, warehouse_type: str) -> str:
    """Sintaxis para LIMIT / TOP segun el warehouse.

    BigQuery/Snowflake/Redshift: LIMIT n
    (TOP n solo es T-SQL, no se usa en estos 3 warehouses)
    """
    if limit <= 0:
        raise ValueError(f"top_n: limit debe ser > 0, recibio {limit}")
    return f"LIMIT {int(limit)}"


# ---- Identifier quoting -----------------------------------------------------

def identifier_quote(name: str, warehouse_type: str) -> str:
    """Devuelve un identificador entrecomillado segun el dialecto.

    Snowflake / Redshift: comillas dobles (ANSI SQL, case-sensitive).
    BigQuery / Databricks: backticks (estilo MySQL/Spark).

    Usar SIEMPRE que el nombre venga del schema introspectado o de
    input del usuario, para evitar SQL injection y para que
    identificadores con caracteres especiales (guion, espacio) no
    rompan la query.

    Args:
        name: el identificador crudo (sin comillas).
        warehouse_type: uno de los dialectos soportados.

    Returns:
        El identificador entrecomillado listo para interpolar en la query.
    """
    wh = dialect_for(warehouse_type)
    if wh in ("bigquery", "databricks"):
        return f"`{name}`"
    return f'"{name}"'