"""
Unit tests para `skills/sql-cloud-warehouse/recetas/connect.py`,
foco en dispatch de auth_method (ADR-003) y detect_auth_method.

Los flows OAuth reales requieren red + credenciales validas, asi que
los tests de _connect_snowflake_oauth y _connect_databricks_service_principal
se limitan a verificar:
  - Que las env vars requeridas se validan (MissingCredentialsError).
  - Que las deps faltantes disparan MissingDependencyError accionable.
  - Que el dispatch elige el flow correcto segun auth_method.

Los tests NO ejecutan el flow completo (no hacemos SELECT 1 contra
un warehouse real). Eso queda cubierto por `make test-snowflake` /
`make test-databricks` (skipped si no hay credenciales).
"""

from __future__ import annotations

import pytest

from sql_cloud_warehouse import recetas as scw


# -----------------------------------------------------------------------
# detect_auth_method
# -----------------------------------------------------------------------

class TestDetectAuthMethod:

    def test_unsupported_warehouse_raises(self) -> None:
        """Solo snowflake y databricks tienen multi-auth."""
        with pytest.raises(ValueError, match=r"solo aplica"):
            scw.detect_auth_method("bigquery")

    def test_unknown_explicit_method_raises(self) -> None:
        """auth_method explicito debe ser uno de los 4 conocidos."""
        with pytest.raises(ValueError, match=r"no soportado"):
            scw.detect_auth_method("snowflake", auth_method="magic-link")

    # --- Snowflake ---

    def test_snowflake_defaults_to_password(self) -> None:
        """Sin SNOWFLAKE_OAUTH_TOKEN → password (default backward-compat)."""
        env = {"SNOWFLAKE_ACCOUNT": "x", "SNOWFLAKE_USER": "u"}
        assert scw.detect_auth_method("snowflake", env=env) == "password"

    def test_snowflake_oauth_when_token_present(self) -> None:
        """Si SNOWFLAKE_OAUTH_TOKEN esta seteado → oauth."""
        env = {"SNOWFLAKE_OAUTH_TOKEN": "abc123"}
        assert scw.detect_auth_method("snowflake", env=env) == "oauth"

    def test_snowflake_oauth_empty_string_falls_back_to_password(self) -> None:
        """SNOWFLAKE_OAUTH_TOKEN='' (vacio) NO triggea OAuth → password."""
        env = {"SNOWFLAKE_OAUTH_TOKEN": ""}
        assert scw.detect_auth_method("snowflake", env=env) == "password"

    def test_snowflake_explicit_password_overrides_oauth_env(self) -> None:
        """Si el caller fuerza 'password' aunque SNOWFLAKE_OAUTH_TOKEN este
        seteado, gana el override explicito (el caller sabe lo que hace)."""
        env = {"SNOWFLAKE_OAUTH_TOKEN": "abc123"}
        assert scw.detect_auth_method(
            "snowflake", env=env, auth_method="password"
        ) == "password"

    def test_snowflake_explicit_oauth_overrides_missing_env(self) -> None:
        """Si el caller fuerza 'oauth' pero SNOWFLAKE_OAUTH_TOKEN no esta
        seteado, gana el override. _connect_snowflake_oauth despues levanta
        MissingCredentialsError con la lista de env vars faltantes."""
        assert scw.detect_auth_method(
            "snowflake", env={}, auth_method="oauth"
        ) == "oauth"

    # --- Databricks ---

    def test_databricks_defaults_to_pat(self) -> None:
        """Sin client credentials → pat (default backward-compat)."""
        env = {"DATABRICKS_SERVER_HOSTNAME": "x"}
        assert scw.detect_auth_method("databricks", env=env) == "pat"

    def test_databricks_service_principal_when_all_three_vars_present(self) -> None:
        """Si los 3 vars (CLIENT_ID + SECRET + OIDC_ENDPOINT) estan
        seteados → service_principal."""
        env = {
            "DATABRICKS_CLIENT_ID": "abc",
            "DATABRICKS_CLIENT_SECRET": "xyz",
            "DATABRICKS_OIDC_ENDPOINT": "https://example/oidc/v1/token",
        }
        assert scw.detect_auth_method("databricks", env=env) == "service_principal"

    def test_databricks_partial_service_principal_falls_back_to_pat(self) -> None:
        """Si falta solo 1 de los 3 vars → cae a pat (no asume parcial)."""
        env = {
            "DATABRICKS_CLIENT_ID": "abc",
            "DATABRICKS_CLIENT_SECRET": "xyz",
            # falta DATABRICKS_OIDC_ENDPOINT
        }
        assert scw.detect_auth_method("databricks", env=env) == "pat"

    def test_databricks_explicit_pat_overrides_service_principal_env(self) -> None:
        """Caller puede forzar pat aunque los vars de SP esten."""
        env = {
            "DATABRICKS_CLIENT_ID": "abc",
            "DATABRICKS_CLIENT_SECRET": "xyz",
            "DATABRICKS_OIDC_ENDPOINT": "https://example/oidc/v1/token",
        }
        assert scw.detect_auth_method(
            "databricks", env=env, auth_method="pat"
        ) == "pat"


# -----------------------------------------------------------------------
# connect_warehouse — dispatch por auth_method
# -----------------------------------------------------------------------

class TestConnectWarehouseDispatch:

    def test_snowflake_oauth_missing_env_raises(self, monkeypatch) -> None:
        """Sin SNOWFLAKE_OAUTH_TOKEN ni SNOWFLAKE_PASSWORD → MissingCredentialsError
        con la lista completa de env vars faltantes (incluye OAuth token)."""
        # Limpiamos env vars que podrian hacer que el test pase por accidente.
        for k in ("SNOWFLAKE_OAUTH_TOKEN", "SNOWFLAKE_PASSWORD",
                  "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER",
                  "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE"):
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(scw.MissingCredentialsError) as exc:
            scw.connect_warehouse("snowflake", auth_method="oauth")
        assert "SNOWFLAKE_OAUTH_TOKEN" in str(exc.value)
        assert "SNOWFLAKE_ACCOUNT" in str(exc.value)

    def test_snowflake_password_missing_env_raises(self, monkeypatch) -> None:
        """Sin env vars de password → MissingCredentialsError."""
        for k in ("SNOWFLAKE_PASSWORD", "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER",
                  "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE"):
            monkeypatch.delenv(k, raising=False)
        monkeypatch.delenv("SNOWFLAKE_OAUTH_TOKEN", raising=False)
        with pytest.raises(scw.MissingCredentialsError) as exc:
            scw.connect_warehouse("snowflake", auth_method="password")
        assert "SNOWFLAKE_PASSWORD" in str(exc.value)

    def test_snowflake_unknown_auth_method_raises(self) -> None:
        """auth_method no soportado para Snowflake → ValueError explicito."""
        with pytest.raises(ValueError, match=r"no soportado"):
            scw.connect_warehouse("snowflake", auth_method="magic-link")

    def test_databricks_unknown_auth_method_raises(self) -> None:
        """auth_method no soportado para Databricks → ValueError explicito."""
        with pytest.raises(ValueError, match=r"no soportado"):
            scw.connect_warehouse("databricks", auth_method="oauth")

    def test_databricks_service_principal_missing_env_raises(self, monkeypatch) -> None:
        """Sin los 3 vars de SP → MissingCredentialsError."""
        for k in ("DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET",
                  "DATABRICKS_OIDC_ENDPOINT", "DATABRICKS_SERVER_HOSTNAME",
                  "DATABRICKS_HTTP_PATH"):
            monkeypatch.delenv(k, raising=False)
        with pytest.raises(scw.MissingCredentialsError) as exc:
            scw.connect_warehouse("databricks", auth_method="service_principal")
        assert "DATABRICKS_CLIENT_ID" in str(exc.value)
        assert "DATABRICKS_CLIENT_SECRET" in str(exc.value)
        assert "DATABRICKS_OIDC_ENDPOINT" in str(exc.value)

    def test_bigquery_rejects_auth_method(self, monkeypatch) -> None:
        """BigQuery no tiene multi-auth → ValueError si el caller fuerza auth_method."""
        monkeypatch.setenv("WAREHOUSE_PROJECT", "x")
        monkeypatch.setenv("WAREHOUSE_DATASET", "y")
        with pytest.raises(ValueError, match=r"BigQuery no soporta auth_method"):
            scw.connect_warehouse("bigquery", auth_method="oauth")

    def test_redshift_rejects_auth_method(self, monkeypatch) -> None:
        """Redshift no tiene multi-auth en v1 → ValueError si el caller fuerza auth_method."""
        for k in ("REDSHIFT_HOST", "REDSHIFT_PORT", "REDSHIFT_USER",
                  "REDSHIFT_PASSWORD", "REDSHIFT_DATABASE"):
            monkeypatch.setenv(k, "x")
        with pytest.raises(ValueError, match=r"Redshift no soporta auth_method"):
            scw.connect_warehouse("redshift", auth_method="password")


# -----------------------------------------------------------------------
# MissingDependencyError cuando el driver no esta instalado
# -----------------------------------------------------------------------

class TestMissingDependencyForOAuth:

    def test_snowflake_oauth_missing_driver_raises(self, monkeypatch) -> None:
        """Si snowflake-connector-python no esta instalado, OAuth flow
        tambien emite MissingDependencyError (mismo deps que password)."""
        monkeypatch.setenv("SNOWFLAKE_OAUTH_TOKEN", "fake-token")
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "x")
        monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "w")
        monkeypatch.setenv("SNOWFLAKE_DATABASE", "d")

        # Simulamos que el import falla via sys.modules monkeypatch.
        import sys
        original = sys.modules.pop("snowflake.sqlalchemy", None)
        original2 = sys.modules.pop("snowflake", None)
        sys.modules["snowflake.sqlalchemy"] = None  # type: ignore
        sys.modules["snowflake"] = None  # type: ignore
        try:
            with pytest.raises(scw.MissingDependencyError) as exc:
                scw.connect_warehouse("snowflake", auth_method="oauth")
            assert "snowflake-connector-python" in str(exc.value)
        finally:
            if original is not None:
                sys.modules["snowflake.sqlalchemy"] = original
            if original2 is not None:
                sys.modules["snowflake"] = original2

    def test_databricks_service_principal_missing_sdk_raises(self, monkeypatch) -> None:
        """Si databricks-sdk no esta instalado, SP flow emite MissingDependencyError
        con 'pip install databricks-sdk' como hint."""
        monkeypatch.setenv("DATABRICKS_SERVER_HOSTNAME", "x")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/p")
        monkeypatch.setenv("DATABRICKS_CLIENT_ID", "id")
        monkeypatch.setenv("DATABRICKS_CLIENT_SECRET", "sec")
        monkeypatch.setenv("DATABRICKS_OIDC_ENDPOINT", "https://x/oidc/v1/token")

        import sys
        original = sys.modules.pop("databricks.sdk.core", None)
        sys.modules["databricks.sdk.core"] = None  # type: ignore
        try:
            with pytest.raises(scw.MissingDependencyError) as exc:
                scw.connect_warehouse("databricks", auth_method="service_principal")
            assert "databricks-sdk" in str(exc.value)
        finally:
            if original is not None:
                sys.modules["databricks.sdk.core"] = original
