"""
Redaction de PII via regex configurables.

Patrones default:
- email: user@domain.tld
- RUT chileno: 12.345.678-9 o 12345678-9 (con o sin puntos)
- telefono CL: +56 9 XXXX XXXX, +56 2 XXXX XXXX, 9 XXXX XXXX
- tarjeta de credito: 16 digitos (con o sin espacios/guiones)

El usuario puede agregar regex custom via `set_extra_patterns(...)`
o env var `AUDIT_LOG_REDACT_REGEX` (separados por `|`).

El texto redactado se reemplaza por `***REDACTED:<nombre>***` para
que el lector del log sepa qué se redactó sin ver el valor original.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PiiPattern:
    name: str
    regex: str
    enabled: bool = True


DEFAULT_PATTERNS: list[PiiPattern] = [
    PiiPattern("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # RUT chileno: 1-2 digitos, opcional puntos, 3 digitos, opcional puntos, 3 digitos, guion, 1 digito o K
    PiiPattern("rut_cl", r"\b\d{1,2}\.?\d{3}\.?\d{3}[-][\dkK]\b"),
    # Tarjeta: 4 grupos de 4 digitos separados por espacio o guion.
    # IMPORTANTE: va ANTES de phone_cl. Una tarjeta de 16 digitos contiene
    # subsecuencias que matchean el patron de telefono (8 digitos con espacio);
    # si phone_cl corre primero, redacciona parcialmente y rompe el match
    # de credit_card. Ordenar credit_card primero preserva la redaccion
    # completa del PAN.
    PiiPattern("credit_card", r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    # Telefono CL: +56 9 XXXX XXXX (con o sin espacios), o 9 XXXX XXXX nacional
    PiiPattern("phone_cl", r"(?:\+?56\s?)?(?:9\s?)?[2-9]\d{3}\s?\d{4}\b"),
]

_extra_patterns: list[PiiPattern] = []


def set_extra_patterns(extra: list[PiiPattern]) -> None:
    """Agrega patrones custom (los reemplaza completamente)."""
    global _extra_patterns
    _extra_patterns = list(extra)


def _active_patterns() -> list[PiiPattern]:
    """Devuelve los patrones activos (default + extra desde env)."""
    patterns = [p for p in DEFAULT_PATTERNS if p.enabled]
    patterns.extend(_extra_patterns)
    env_extra = os.environ.get("AUDIT_LOG_REDACT_REGEX", "")
    if env_extra:
        # Formato: "nombre1:regex1|nombre2:regex2|..."
        for chunk in env_extra.split("|"):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            name, _, regex = chunk.partition(":")
            patterns.append(PiiPattern(name=name.strip(), regex=regex.strip()))
    return patterns


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Redacta PII en el texto. Devuelve (texto_redactado, lista_nombres).

    Si el texto es None, devuelve ("", []).
    """
    if not text:
        return text or "", []

    redacted = text
    redacted_fields: list[str] = []

    for pat in _active_patterns():
        try:
            new_text, n = re.subn(
                pat.regex,
                f"***REDACTED:{pat.name}***",
                redacted,
            )
            if n > 0:
                redacted = new_text
                if pat.name not in redacted_fields:
                    redacted_fields.append(pat.name)
        except re.error:
            # Regex invalida del usuario — la salteamos silenciosamente
            continue

    return redacted, redacted_fields