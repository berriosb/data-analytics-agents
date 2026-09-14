"""
Export a PDF ejecutivo via WeasyPrint (con fallback a pdfkit si GTK no esta).

El PDF se arma en 3 pasos:
1. Render HTML+CSS con sustitucion de placeholders en el template
2. Convertir HTML a PDF con WeasyPrint
3. Si WeasyPrint falla por dependencias GTK (comun en Linux), usar pdfkit
"""

from __future__ import annotations

import base64
import shutil
import subprocess
from pathlib import Path
from typing import Any


def build_pdf(insights: dict[str, Any], charts: list[Path],
              template_dir: str | Path, output: str | Path,
              logo: str | Path | None = None) -> Path:
    """Construye el PDF ejecutivo y devuelve el path final.

    Args:
        insights: dict normalizado de parse_insights_markdown()
        charts: lista de paths a graficos (PNG/SVG/HTML de Plotly)
        template_dir: directorio que contiene executive_pdf.html y styles.css
        output: ruta destino del PDF (puede no existir)
        logo: path opcional a un PNG para la portada

    Raises:
        RuntimeError si WeasyPrint y pdfkit fallan
    """
    template_dir = Path(template_dir)
    html_template = template_dir / "executive_pdf.html"
    css_file = template_dir / "styles.css"
    if not html_template.exists():
        raise FileNotFoundError(f"No existe template HTML: {html_template}")
    if not css_file.exists():
        raise FileNotFoundError(f"No existe styles.css: {css_file}")

    css = css_file.read_text(encoding="utf-8")
    html = _render_html(
        html_template.read_text(encoding="utf-8"), css, insights, charts, logo
    )
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Intento 1: WeasyPrint
    try:
        import weasyprint
        weasyprint.HTML(string=html, base_url=str(template_dir)).write_pdf(
            target=str(output)
        )
        return output
    except Exception as weasy_err:
        # Intento 2: pdfkit (requiere wkhtmltopdf)
        if shutil.which("wkhtmltopdf"):
            try:
                import pdfkit
                pdfkit.from_string(html, str(output))
                return output
            except Exception as pdfkit_err:
                raise RuntimeError(
                    f"PDF export fallo. WeasyPrint: {weasy_err}. "
                    f"pdfkit: {pdfkit_err}. "
                    "Instala WeasyPrint con deps GTK o wkhtmltopdf para pdfkit."
                ) from pdfkit_err
        raise RuntimeError(
            f"WeasyPrint fallo ({weasy_err}) y wkhtmltopdf no esta instalado "
            "(pdfkit requiere wkhtmltopdf binario). "
            "En Debian/Ubuntu: sudo apt install libpango-1.0-0 libpangoft2-1.0-0 "
            "para que WeasyPrint funcione, o sudo apt install wkhtmltopdf para pdfkit."
        ) from weasy_err


def _render_html(html_template: str, css: str, insights: dict[str, Any],
                 charts: list[Path], logo: str | Path | None) -> str:
    """Sustituye placeholders {{...}} en el template HTML.

    Placeholders soportados:
        {{styles}}, {{title}}, {{date}}, {{author}}
        {{summary_html}}, {{insights_html}}, {{charts_html}}
        {{logo_data_uri}}, {{logo_data_uri_html}}
    """
    summary_text = insights.get("summary", "")
    summary_html = (f'<p class="summary-html">{_esc(summary_text)}</p>'
                    if summary_text else "")
    logo_data = _data_uri(logo) if logo else ""
    logo_html = (f'<img src="{logo_data}" alt="Logo" class="cover-logo" />'
                 if logo_data else "")

    replacements = {
        "{{styles}}": css,
        "{{title}}": _esc(insights.get("title", "Reporte")),
        "{{date}}": _esc(insights.get("date", "")),
        "{{author}}": _esc(insights.get("author", "")),
        "{{summary_html}}": summary_html,
        "{{insights_html}}": _render_insights_html(insights.get("insights", [])),
        "{{charts_html}}": _render_charts_html(charts),
        "{{logo_data_uri}}": logo_data,
        "{{logo_data_uri_html}}": logo_html,
    }
    html = html_template
    for k, v in replacements.items():
        html = html.replace(k, v)
    return html


def _render_insights_html(insights: list[dict[str, Any]]) -> str:
    if not insights:
        return "<p><em>Sin insights numerados en el markdown de origen.</em></p>"
    blocks = []
    for ins in insights:
        b = (
            f'<section class="insight">'
            f'<h3 class="insight-title">Insight {ins["number"]}: '
            f'{_esc(ins["title"])}</h3>'
        )
        if ins.get("what"):
            b += f'<p><strong>Qué:</strong> {_esc(ins["what"])}</p>'
        if ins.get("why"):
            b += f'<p><strong>Por qué:</strong> {_esc(ins["why"])}</p>'
        if ins.get("now"):
            b += f'<p><strong>Ahora qué:</strong> {_esc(ins["now"])}</p>'
        if not (ins.get("what") or ins.get("why") or ins.get("now")):
            b += f'<p>{_esc(ins["title"])}</p>'
        b += "</section>"
        blocks.append(b)
    return "\n".join(blocks)


def _render_charts_html(charts: list[Path]) -> str:
    from .render_plotly import chart_to_png_bytes

    if not charts:
        return "<p><em>Sin graficos en el directorio.</em></p>"
    blocks = []
    for i, c in enumerate(charts, start=1):
        try:
            png = chart_to_png_bytes(c)
            data = base64.b64encode(png).decode("ascii")
            ext = "svg+xml" if c.suffix.lower() == ".svg" else "png"
            img_src = f"data:image/{ext};base64,{data}"
        except Exception as e:
            blocks.append(
                f'<section class="chart chart-error">'
                f'<h3 class="chart-title">Figura {i}: {_esc(c.name)}</h3>'
                f'<p class="chart-error">No se pudo renderizar: {e}</p>'
                f"</section>"
            )
            continue
        blocks.append(
            f'<section class="chart">'
            f'<h3 class="chart-title">Figura {i}: {_esc(c.stem)}</h3>'
            f'<img src="{img_src}" alt="{_esc(c.stem)}" />'
            f"</section>"
        )
    return "\n".join(blocks)


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _data_uri(path: str | Path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    suffix = p.suffix.lower()
    mime = "image/png" if suffix == ".png" else f"image/{suffix.lstrip('.')}"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")