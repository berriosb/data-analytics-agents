"""
Conexion a Snowflake, BigQuery, Redshift o Databricks via SQLAlchemy + driver oficial.

Las deps cloud son OPCIONALES (peerDeps). Si no estan instaladas, la skill
emite MissingDependencyError con un comando pip install accionable.

Credenciales via os.environ (sin secrets hardcodeados):

Snowflake (ADR-001, ampliado en ADR-003):
- Password:   SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
              SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, [SNOWFLAKE_SCHEMA]
- OAuth:      SNOWFLAKE_OAUTH_TOKEN (access token ya emitido por el IdP)
              + SNOWFLAKE_ACCOUNT, SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE
              El caller maneja el flow completo con su IdP (Okta / Azure AD).

BigQuery (ADR-001):
- Service account JSON via GOOGLE_APPLICATION_CREDENTIALS (path al JSON).
  Cubre el rol de OAuth — no hay flujo OAuth adicional en v1.

Redshift (ADR-001):
- Password:   REDSHIFT_HOST, REDSHIFT_PORT, REDSHIFT_USER, REDSHIFT_PASSWORD,
              REDSHIFT_DATABASE

Databricks (ADR-001, ampliado en ADR-003):
- PAT:               DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH,
                     DATABRICKS_TOKEN
- Service principal: DATABRICKS_SERVER_HOSTNAME, DATABRICKS_HTTP_PATH,
                     DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET,
                     DATABRICKS_OIDC_ENDPOINT
                     (client credentials flow via databricks-sdk)
"""

from __future__ import annotations

import os
from typing import Any, Literal

try:
    from sqlalchemy.engine import Engine
except ImportError:
    Engine = Any  # type: ignore

from .errors import MissingCredentialsError, MissingDependencyError


SUPPORTED = ("snowflake", "bigquery", "redshift", "databricks")

AuthMethod = Literal["password", "oauth", "pat", "service_principal"]


def detect_auth_method(
    warehouse_type: str,
    env: dict[str, str] | None = None,
    *,
    auth_method: str | None = None,
) -> str:
    """Decide que metodo de autenticacion usar para un warehouse.

    Si el caller pasa `auth_method` explicito, se respeta. Si no, auto-
    detecta basado en que env vars estan seteadas:

    Snowflake:
      - 'oauth' si SNOWFLAKE_OAUTH_TOKEN esta seteado.
      - 'password' en cualquier otro caso (default).

    Databricks:
      - 'service_principal' si DATABRICKS_CLIENT_ID + DATABRICKS_CLIENT_SECRET
        + DATABRICKS_OIDC_ENDPOINT estan seteados.
      - 'pat' en cualquier otro caso (default).

    BigQuery / Redshift:
      - Solo soportan un metodo, no hay auto-deteccion.

    Args:
        warehouse_type: 'snowflake' | 'databricks' (los unicos con multi-auth).
        env: dict de env vars (default os.environ).
        auth_method: forzar un metodo ('oauth' | 'password' | 'pat' |
            'service_principal'). Default: auto-detectar.

    Returns:
        El metodo de autenticacion resuelto.

    Raises:
        ValueError si el warehouse no soporta multi-auth o si auth_method
        es desconocido.
    """
    if warehouse_type not in ("snowflake", "databricks"):
        raise ValueError(
            f"detect_auth_method solo aplica a snowflake / databricks; "
            f"recibi '{warehouse_type}'."
        )
    if auth_method is not None:
        if auth_method not in ("password", "oauth", "pat", "service_principal"):
            raise ValueError(
                f"auth_method '{auth_method}' no soportado. "
                "Usar uno de: password, oauth, pat, service_principal."
            )
        return auth_method

    e = env if env is not None else dict(os.environ)
    if warehouse_type == "snowflake":
        if "SNOWFLAKE_OAUTH_TOKEN" in e and e["SNOWFLAKE_OAUTH_TOKEN"]:
            return "oauth"
        return "password"
    # databricks
    if all(k in e and e[k] for k in (
        "DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET", "DATABRICKS_OIDC_ENDPOINT",
    )):
        return "service_principal"
    return "pat"


def connect_warehouse(
    warehouse_type: str | None = None,
    *,
    auth_method: str | None = None,
    **overrides: Any,
) -> Engine:
    """Construye un SQLAlchemy Engine para el warehouse.

    Args:
        warehouse_type: 'snowflake' | 'bigquery' | 'redshift' | 'databricks'.
            Si None, lee WAREHOUSE_TYPE de os.environ.
        auth_method: forzar un metodo de autenticacion ('password' | 'oauth'
            para Snowflake, 'pat' | 'service_principal' para Databricks).
            Default: auto-detectar via detect_auth_method().
        **overrides: parametros especificos por warehouse (ej. account,
            database, catalog) que toman precedencia sobre env.

    Raises:
        MissingCredentialsError si faltan env vars
        MissingDependencyError si el driver no esta instalado
        ValueError si el warehouse o auth_method no son validos.
    """
    wh = (warehouse_type or os.environ.get("WAREHOUSE_TYPE", "")).lower()
    if wh not in SUPPORTED:
        raise ValueError(
            f"WAREHOUSE_TYPE debe ser uno de {SUPPORTED}, recibio '{wh}'. "
            "Configura la env var WAREHOUSE_TYPE o pasala explicita."
        )

    if wh == "snowflake":
        method = detect_auth_method("snowflake", auth_method=auth_method)
        return _connect_snowflake(overrides, auth_method=method)
    if wh == "bigquery":
        if auth_method is not None:
            raise ValueError("BigQuery no soporta auth_method explicito; usa service account JSON.")
        return _connect_bigquery(overrides)
    if wh == "redshift":
        if auth_method is not None:
            raise ValueError("Redshift no soporta auth_method explicito en v1.")
        return _connect_redshift(overrides)
    if wh == "databricks":
        method = detect_auth_method("databricks", auth_method=auth_method)
        return _connect_databricks(overrides, auth_method=method)
    raise ValueError(f"Warehouse no soportado: {wh}")  # unreachable


def get_engine(
    warehouse_type: str | None = None,
    *,
    auth_method: str | None = None,
) -> Engine:
    """Alias de connect_warehouse para tests. Pasa auth_method si se da."""
    return connect_warehouse(warehouse_type, auth_method=auth_method)


def test_connection(engine: Engine) -> bool:
    """Ejecuta SELECT 1 para validar que la conexion funciona.

    Returns True si responde. Levanta la excepcion original si falla.
    """
    with engine.connect() as conn:
        result = conn.exec_driver_sql("SELECT 1").scalar()
        return result == 1


# ---- Snowflake --------------------------------------------------------------

def _connect_snowflake(
    overrides: dict[str, Any],
    *,
    auth_method: str = "password",
) -> Engine:
    """Conexion a Snowflake. Dispatch por auth_method."""
    if auth_method == "oauth":
        return _connect_snowflake_oauth(overrides)
    if auth_method == "password":
        return _connect_snowflake_password(overrides)
    raise ValueError(
        f"Snowflake auth_method '{auth_method}' no soportado; usar 'password' o 'oauth'."
    )


def _connect_snowflake_password(overrides: dict[str, Any]) -> Engine:
    """Snowflake con user/password (flow legacy de v0.4.0)."""
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
                "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE"]
    creds = _gather_creds(required, "snowflake", overrides)

    try:
        from snowflake.sqlalchemy import URL
        from sqlalchemy import create_engine
    except ImportError as e:
        raise MissingDependencyError(
            "snowflake-connector-python",
            "snowflake-connector-python '>=3.0'",
        ) from e

    url = URL(
        account=creds["SNOWFLAKE_ACCOUNT"],
        user=creds["SNOWFLAKE_USER"],
        password=creds["SNOWFLAKE_PASSWORD"],
        warehouse=creds["SNOWFLAKE_WAREHOUSE"],
        database=creds["SNOWFLAKE_DATABASE"],
        schema=creds.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
    )
    return create_engine(url, connect_args={"client_session_keep_alive": True})


def _connect_snowflake_oauth(overrides: dict[str, Any]) -> Engine:
    """Snowflake con OAuth (external IdP, ADR-003).

    El caller es responsable de obtener el access token via su IdP
    corporativo (Okta / Azure AD / Google Workspace) y setearlo en
    SNOWFLAKE_OAUTH_TOKEN. La skill NO maneja el flow completo de
    OAuth (authorization code, refresh) — eso es responsabilidad del
    IdP integration layer del caller.

    Para refresh automatico de tokens, ver SNOWFLAKE_OAUTH_CLIENT_ID +
    SNOWFLAKE_OAUTH_CLIENT_SECRET + SNOWFLAKE_OAUTH_REFRESH_TOKEN (v1.x).
    """
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_OAUTH_TOKEN",
                "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE"]
    creds = _gather_creds(required, "snowflake", overrides)

    try:
        from snowflake.sqlalchemy import URL
        from sqlalchemy import create_engine
    except ImportError as e:
        raise MissingDependencyError(
            "snowflake-connector-python",
            "snowflake-connector-python '>=3.0'",
        ) from e

    url = URL(
        account=creds["SNOWFLAKE_ACCOUNT"],
        warehouse=creds["SNOWFLAKE_WAREHOUSE"],
        database=creds["SNOWFLAKE_DATABASE"],
        schema=creds.get("SNOWFLAKE_SCHEMA", "PUBLIC"),
    )
    # Authenticator='oauth' le dice al connector que use el token de
    # connect_args en lugar de user/password. El token NO va en la URL.
    return create_engine(
        url,
        connect_args={
            "client_session_keep_alive": True,
            "authenticator": "oauth",
            "token": creds["SNOWFLAKE_OAUTH_TOKEN"],
        },
    )


# ---- BigQuery ---------------------------------------------------------------

def _connect_bigquery(overrides: dict[str, Any]) -> Engine:
    required = ["WAREHOUSE_PROJECT", "WAREHOUSE_DATASET"]
    creds = _gather_creds(required, "bigquery", overrides)

    try:
        from sqlalchemy_bigquery import BigQueryDialect  # noqa: F401
        from sqlalchemy import create_engine
    except ImportError as e:
        raise MissingDependencyError(
            "sqlalchemy-bigquery",
            "sqlalchemy-bigquery google-cloud-bigquery '>=3.0'",
        ) from e

    # sqlalchemy-bigquery usa URLs tipo bigquery://project/dataset
    return create_engine(
        f"bigquery://{creds['WAREHOUSE_PROJECT']}/{creds['WAREHOUSE_DATASET']}"
    )


# ---- Redshift ---------------------------------------------------------------

def _connect_redshift(overrides: dict[str, Any]) -> Engine:
    required = ["REDSHIFT_HOST", "REDSHIFT_PORT", "REDSHIFT_USER",
                "REDSHIFT_PASSWORD", "REDSHIFT_DATABASE"]
    creds = _gather_creds(required, "redshift", overrides)

    try:
        from sqlalchemy_redshift import register_dialect  # noqa: F401
        from sqlalchemy import create_engine
    except ImportError as e:
        raise MissingDependencyError(
            "sqlalchemy-redshift",
            "sqlalchemy-redshift redshift-connector '>=2.0'",
        ) from e

    from urllib.parse import quote_plus
    host = creds["REDSHIFT_HOST"]
    port = creds["REDSHIFT_PORT"]
    user = quote_plus(creds["REDSHIFT_USER"])
    pwd = quote_plus(creds["REDSHIFT_PASSWORD"])
    db = creds["REDSHIFT_DATABASE"]
    url = f"redshift+redshift_connector://{user}:{pwd}@{host}:{port}/{db}"
    return create_engine(url)


# ---- Databricks -------------------------------------------------------------

def _connect_databricks(
    overrides: dict[str, Any],
    *,
    auth_method: str = "pat",
) -> Engine:
    """Conexion a Databricks. Dispatch por auth_method."""
    if auth_method == "service_principal":
        return _connect_databricks_service_principal(overrides)
    if auth_method == "pat":
        return _connect_databricks_pat(overrides)
    raise ValueError(
        f"Databricks auth_method '{auth_method}' no soportado; "
        "usar 'pat' o 'service_principal'."
    )


def _connect_databricks_pat(overrides: dict[str, Any]) -> Engine:
    """Databricks con Personal Access Token (flow legacy de v0.9.0)."""
    required = ["DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH", "DATABRICKS_TOKEN"]
    creds = _gather_creds(required, "databricks", overrides)

    try:
        from databricks import sqlalchemy as databricks_sa  # noqa: F401
        from sqlalchemy import create_engine
    except ImportError:
        try:
            from databricks import sql as databricks_sql  # noqa: F401
            from sqlalchemy import create_engine
        except ImportError as e:
            raise MissingDependencyError(
                "databricks-sql-connector",
                "databricks-sql-connector databricks-sqlalchemy",
            ) from e

    host = creds["DATABRICKS_SERVER_HOSTNAME"].replace("https://", "").strip("/")
    http_path = creds["DATABRICKS_HTTP_PATH"]
    token = creds["DATABRICKS_TOKEN"]
    catalog = overrides.get("DATABRICKS_CATALOG") or os.environ.get("DATABRICKS_CATALOG", "")
    schema = overrides.get("DATABRICKS_SCHEMA") or os.environ.get("DATABRICKS_SCHEMA", "")

    url = f"databricks://token:{token}@{host}?http_path={http_path}"
    if catalog:
        url += f"&catalog={catalog}"
    if schema:
        url += f"&schema={schema}"

    return create_engine(url)


def _connect_databricks_service_principal(overrides: dict[str, Any]) -> Engine:
    """Databricks con service principal OAuth (client credentials flow).

    Usa `databricks-sdk` para hacer el client credentials flow contra
    el OIDC endpoint del Databricks workspace y obtener un access
    token. Despues pasa el token al connector via la URL estandar.

    Env vars requeridas:
      - DATABRICKS_SERVER_HOSTNAME
      - DATABRICKS_HTTP_PATH
      - DATABRICKS_CLIENT_ID
      - DATABRICKS_CLIENT_SECRET
      - DATABRICKS_OIDC_ENDPOINT  (ej. https://<workspace>.databricks.com/oidc/v1/token)
    """
    required = [
        "DATABRICKS_SERVER_HOSTNAME", "DATABRICKS_HTTP_PATH",
        "DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET", "DATABRICKS_OIDC_ENDPOINT",
    ]
    creds = _gather_creds(required, "databricks", overrides)

    try:
        from databricks.sdk.core import Config  # type: ignore
    except ImportError as e:
        raise MissingDependencyError(
            "databricks-sdk",
            "databricks-sdk",
        ) from e

    # El SDK hace el client_credentials flow y devuelve un access token
    # que rotamos automaticamente via el host del workspace.
    cfg = Config(
        host=f"https://{creds['DATABRICKS_SERVER_HOSTNAME'].replace('https://', '').strip('/')}",
        client_id=creds["DATABRICKS_CLIENT_ID"],
        client_secret=creds["DATABRICKS_CLIENT_SECRET"],
        oidc_endpoint=creds["DATABRICKS_OIDC_ENDPOINT"],
    )
    # .as_dict() devuelve las credenciales resueltas, incluyendo el
    # access token rotado automaticamente.
    sdk_creds = cfg.as_dict()
    token = sdk_creds["token"]

    catalog = overrides.get("DATABRICKS_CATALOG") or os.environ.get("DATABRICKS_CATALOG", "")
    schema = overrides.get("DATABRICKS_SCHEMA") or os.environ.get("DATABRICKS_SCHEMA", "")

    host = creds["DATABRICKS_SERVER_HOSTNAME"].replace("https://", "").strip("/")
    http_path = creds["DATABRICKS_HTTP_PATH"]
    url = f"databricks://token:{token}@{host}?http_path={http_path}"
    if catalog:
        url += f"&catalog={catalog}"
    if schema:
        url += f"&schema={schema}"

    try:
        from sqlalchemy import create_engine
    except ImportError as e:
        raise MissingDependencyError(
            "sqlalchemy",
            "sqlalchemy",
        ) from e

    return create_engine(url)


# ---- helpers ---------------------------------------------------------------

def _gather_creds(required: list[str], warehouse: str,
                  overrides: dict[str, Any]) -> dict[str, str]:
    """Lee env vars requeridas, aplica overrides, valida."""
    out: dict[str, str] = {}
    missing: list[str] = []
    for key in required:
        val = overrides.get(key) or os.environ.get(key, "")
        if not val:
            missing.append(key)
        else:
            out[key] = val
    if missing:
        raise MissingCredentialsError(missing, warehouse)
    return out