"""
Export a HTML standalone con graficos embebidos en base64.

Un solo archivo .html que se abre en cualquier browser sin dependencias externas.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from .render_plotly import chart_to_png_bytes


def build_html(insights: dict[str, Any], charts: list[Path],
               template_dir: str | Path, output: str | Path,
               logo: str | Path | None = None) -> Path:
    """Construye el HTML standalone y devuelve el path final."""
    template_dir = Path(template_dir)
    html_template = template_dir / "executive_inline.html"
    css_file = template_dir / "styles.css"
    if not html_template.exists():
        raise FileNotFoundError(f"No existe template HTML: {html_template}")
    if not css_file.exists():
        raise FileNotFoundError(f"No existe styles.css: {css_file}")

    css = css_file.read_text(encoding="utf-8")
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
    html = html_template.read_text(encoding="utf-8")
    for k, v in replacements.items():
        html = html.replace(k, v)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


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
    if not charts:
        return "<p><em>Sin graficos en el directorio.</em></p>"
    blocks = []
    for i, c in enumerate(charts, start=1):
        try:
            data_bytes = chart_to_png_bytes(c)
            data = base64.b64encode(data_bytes).decode("ascii")
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