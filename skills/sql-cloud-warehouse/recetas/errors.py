"""
Errores consistentes con mensajes accionables para sql-cloud-warehouse.
"""


class MissingDependencyError(ImportError):
    """Una dep opcional (driver de cloud) no esta instalada."""

    def __init__(self, package: str, install_hint: str = ""):
        msg = (
            f"Falta la dependencia opcional '{package}'. "
            f"Instalala con: pip install {install_hint or package}"
        )
        super().__init__(msg)
        self.package = package


class MissingCredentialsError(ValueError):
    """Faltan variables de entorno con credenciales del warehouse."""

    def __init__(self, missing: list[str], warehouse: str):
        msg = (
            f"Faltan variables de entorno para {warehouse}: {', '.join(missing)}. "
            "Configuralas via .env o vault antes de conectar. "
            f"Ver skills/sql-cloud-warehouse/SKILL.md seccion 'Credenciales'."
        )
        super().__init__(msg)
        self.missing = missing
        self.warehouse = warehouse