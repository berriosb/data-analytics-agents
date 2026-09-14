"""
Recetas pre-aprobadas para exportar un reporte ejecutivo
(graficos Plotly + insights en markdown) a PDF, PPT o HTML.

Usado por la skill `report-export`. NO contiene codigo dinamico del usuario:
todas las funciones reciben paths validados y devuelven rutas de output.

Modulos:
- parse_insights: extrae titulo, insights numerados, fecha y autor de un MD
- render_plotly: convierte HTML/PNG/SVG de Plotly a PNG con kaleido
- build_pdf: arma HTML+CSS y exporta a PDF con WeasyPrint
- build_ppt: clona template PPTX y agrega slides con python-pptx
- build_html: embebe graficos en base64 + CSS inline (archivo unico)
- verify: valida que el output de cada formato sea correcto
"""

from .parse_insights import parse_insights_markdown
from .render_plotly import collect_charts, plotly_html_to_png
from .build_html import build_html
from .verify import verify_pdf, verify_ppt, verify_html

try:
    from .build_pdf import build_pdf
except ImportError:
    def build_pdf(*args, **kwargs):  # type: ignore
        raise ImportError("Para exportar a PDF, instalá weasyprint: pip install weasyprint")

try:
    from .build_ppt import build_ppt
except ImportError:
    def build_ppt(*args, **kwargs):  # type: ignore
        raise ImportError("Para exportar a PPTX, instalá python-pptx: pip install python-pptx")

__all__ = [
    "parse_insights_markdown",
    "collect_charts",
    "plotly_html_to_png",
    "build_pdf",
    "build_ppt",
    "build_html",
    "verify_pdf",
    "verify_ppt",
    "verify_html",
]