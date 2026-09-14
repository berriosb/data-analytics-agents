"""
Errores consistentes con mensajes accionables para excel-formulas.
"""


class ExcelFormulaError(Exception):
    """No se pudo abrir o procesar el Excel."""

    def __init__(self, message: str, path: str | None = None):
        if path:
            message = f"{message} (path: {path})"
        super().__init__(message)
        self.path = path