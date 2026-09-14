"""
Inicializacion del audit log: crea el directorio y archivo/tabla
con permisos 0600 (solo el usuario puede leer/escribir).
"""

from __future__ import annotations

import os
from pathlib import Path

from .backend import AUDIT_DIR, LOG_FILE, SQLITE_FILE, get_backend


def init_audit_log(backend: str | None = None) -> Path:
    """Crea el directorio y archivo/tabla inicial.

    Args:
        backend: 'jsonl' o 'sqlite'. Si None, lee AUDIT_LOG_BACKEND env var.

    Returns:
        Path al archivo JSONL o SQLite inicializado.
    """
    if backend:
        os.environ["AUDIT_LOG_BACKEND"] = backend

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    # Permisos 0700 en el directorio (solo user)
    AUDIT_DIR.chmod(0o700)

    backend_type = os.environ.get("AUDIT_LOG_BACKEND", "jsonl").lower()
    if backend_type == "sqlite":
        # Forzar creacion de la tabla via el backend
        get_backend()
        if SQLITE_FILE.exists():
            SQLITE_FILE.chmod(0o600)
        return SQLITE_FILE

    # JSONL: crear archivo vacio con permisos 0600
    LOG_FILE.touch()
    LOG_FILE.chmod(0o600)
    return LOG_FILE