"""
Unit tests para `skills/audit-log/recetas/redact.py`.

`redact_pii` es el corazon del cumplimiento (compliance) de audit-log:
antes de escribir cualquier query al log, hay que sacar emails, RUTs,
telefonos y tarjetas. Un bug aqui expone PII en texto claro — serio.

Cobertura:
- Los 4 patrones default (email, RUT CL, telefono CL, tarjeta)
- Patrones custom via `set_extra_patterns` y env var
- Edge cases: texto vacio, multiples PII en el mismo string, overlapping
"""

from __future__ import annotations

import pytest

from audit_log import recetas as al
from audit_log.recetas.redact import (
    PiiPattern,
    set_extra_patterns,
    redact_pii,
)


@pytest.fixture(autouse=True)
def reset_extra_patterns():
    """Resetea los patrones custom despues de cada test para no contaminar."""
    yield
    set_extra_patterns([])


# -----------------------------------------------------------------------
# Patrones default
# -----------------------------------------------------------------------

class TestDefaultPatterns:

    def test_redacts_email(self) -> None:
        text = "Contactame a juan.perez@empresa.cl para mas info"
        out, fields = redact_pii(text)
        assert "juan.perez@empresa.cl" not in out
        assert "email" in fields
        assert "***REDACTED:email***" in out

    def test_redacts_multiple_emails(self) -> None:
        text = "From alice@a.com to bob@b.com CC carol@c.com"
        out, fields = redact_pii(text)
        assert "alice@a.com" not in out
        assert "bob@b.com" not in out
        assert "carol@c.com" not in out
        # Email aparece una sola vez en la lista de fields (dedupe)
        assert fields.count("email") == 1

    def test_redacts_rut_cl_with_dots_and_dash(self) -> None:
        """RUT formato 12.345.678-9 (el canonico)."""
        text = "RUT del cliente: 12.345.678-9"
        out, fields = redact_pii(text)
        assert "12.345.678-9" not in out
        assert "rut_cl" in fields

    def test_redacts_rut_cl_without_dots(self) -> None:
        """RUT formato 12345678-9 (sin puntos)."""
        text = "RUT: 12345678-9"
        out, fields = redact_pii(text)
        assert "12345678-9" not in out
        assert "rut_cl" in fields

    def test_does_not_redact_random_short_numbers_as_rut(self) -> None:
        """Numeros cortos como '123-4' no deben matchear el patron de RUT."""
        text = "telefono corto 123-4"
        out, fields = redact_pii(text)
        # '123-4' tiene 3 digitos antes del guion, no calza con el patron
        assert "123-4" in out
        assert "rut_cl" not in fields

    def test_redacts_phone_cl_with_country_code(self) -> None:
        """Telefono CL formato +56 9 XXXX XXXX."""
        text = "Llamame al +56 9 8765 4321"
        out, fields = redact_pii(text)
        assert "8765 4321" not in out
        assert "phone_cl" in fields

    def test_redacts_credit_card_with_spaces(self) -> None:
        text = "Pago con tarjeta 4532 1234 5678 9010"
        out, fields = redact_pii(text)
        assert "4532 1234 5678 9010" not in out
        assert "credit_card" in fields

    def test_redacts_credit_card_with_dashes(self) -> None:
        text = "Card: 4532-1234-5678-9010 exp 12/27"
        out, fields = redact_pii(text)
        assert "4532-1234-5678-9010" not in out
        assert "credit_card" in fields

    def test_redacts_credit_card_no_separators(self) -> None:
        text = "PAN: 4532123456789010"
        out, fields = redact_pii(text)
        assert "4532123456789010" not in out
        assert "credit_card" in fields


# -----------------------------------------------------------------------
# Edge cases de robustez
# -----------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_string_returns_empty(self) -> None:
        out, fields = redact_pii("")
        assert out == ""
        assert fields == []

    def test_none_input_returns_empty(self) -> None:
        out, fields = redact_pii(None)  # type: ignore[arg-type]
        assert out == ""
        assert fields == []

    def test_text_without_pii_unchanged(self) -> None:
        text = "SELECT COUNT(*) FROM customers WHERE active = TRUE"
        out, fields = redact_pii(text)
        assert out == text
        assert fields == []

    def test_multiple_pii_types_in_same_string(self) -> None:
        text = "Cliente juan@x.com RUT 12.345.678-9 tel +56 9 8765 4321"
        out, fields = redact_pii(text)
        assert "juan@x.com" not in out
        assert "12.345.678-9" not in out
        assert "8765 4321" not in out
        assert set(fields) >= {"email", "rut_cl", "phone_cl"}

    def test_invalid_custom_regex_silently_skipped(self) -> None:
        """Un regex invalido provisto por el usuario no rompe el resto."""
        set_extra_patterns([PiiPattern("broken", "[unclosed")])
        text = "email juan@x.com sigue"
        out, fields = redact_pii(text)
        # Email igual se redacta apesar del regex invalido
        assert "juan@x.com" not in out
        assert "email" in fields
        # El patron broken no aparece porque se salteo
        assert "broken" not in fields


# -----------------------------------------------------------------------
# Custom patterns via API + env var
# -----------------------------------------------------------------------

class TestCustomPatterns:

    def test_set_extra_patterns_adds_redaction(self) -> None:
        """El usuario puede agregar sus propios patrones."""
        set_extra_patterns([PiiPattern(
            name="internal_id",
            regex=r"\bEMP-\d{6}\b",
        )])
        text = "Employee EMP-123456 logged in"
        out, fields = redact_pii(text)
        assert "EMP-123456" not in out
        assert "internal_id" in fields

    def test_env_var_patterns(self, monkeypatch) -> None:
        """Patrones custom via env var AUDIT_LOG_REDACT_REGEX."""
        monkeypatch.setenv(
            "AUDIT_LOG_REDACT_REGEX",
            "api_key:sk-[A-Za-z0-9]{20}",
        )
        text = "Usar api_key:sk-abcdef1234567890abcd en el header"
        out, fields = redact_pii(text)
        assert "sk-abcdef1234567890abcd" not in out
        assert "api_key" in fields

    def test_env_var_malformed_chunk_ignored(self, monkeypatch) -> None:
        """Chunks sin ':' se ignoran silenciosamente (no rompen)."""
        monkeypatch.setenv(
            "AUDIT_LOG_REDACT_REGEX",
            "valid_name:foo|sin_separador|otra:bar",
        )
        text = "foo y bar"
        out, _ = redact_pii(text)
        # Al menos uno de los patterns validos debe haber actuado
        assert "***REDACTED:valid_name***" in out or "***REDACTED:otra***" in out
