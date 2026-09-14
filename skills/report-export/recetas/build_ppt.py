"""
Export a PPTX nativo via python-pptx.

Estructura del PPT:
- Slide 1: Portada (titulo, fecha, autor, logo opcional)
- Slides 2..N+1: una figura por slide (chart embebido como imagen)
- Slide final: Lista de insights como bullets
- Footer con fecha/autor en cada slide via slide master (configurable)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.util import Inches, Pt

from .render_plotly import chart_to_png_bytes


def build_ppt(insights: dict[str, Any], charts: list[Path],
              template_path: str | Path | None, output: str | Path,
              logo: str | Path | None = None) -> Path:
    """Construye el PPTX y devuelve el path final.

    Args:
        insights: dict normalizado de parse_insights_markdown()
        charts: lista de paths a graficos (PNG/SVG/HTML)
        template_path: PPTX template (puede ser None → empieza de cero)
        output: ruta destino del PPTX
        logo: PNG opcional para la portada
    """
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if template_path and Path(template_path).exists():
        prs = Presentation(str(template_path))
    else:
        prs = Presentation()  # default blank template

    # Slide 1: Portada
    _add_cover_slide(prs, insights, logo)

    # Slides de figuras
    for i, chart in enumerate(charts, start=1):
        try:
            png = chart_to_png_bytes(chart)
            _add_chart_slide(prs, f"Figura {i}: {chart.stem}", png, insights)
        except Exception:
            _add_error_slide(prs, f"Figura {i}: {chart.name}",
                             f"No se pudo renderizar {chart.name}")

    # Slide final: insights
    _add_insights_slide(prs, insights)

    prs.save(str(output))
    return output


def _add_cover_slide(prs: Presentation, insights: dict[str, Any],
                     logo: str | Path | None) -> None:
    blank = prs.slide_layouts[6]  # blank layout
    slide = prs.slides.add_slide(blank)
    tx = slide.shapes.add_textbox(Inches(0.5), Inches(2), Inches(9), Inches(2))
    tf = tx.text_frame
    tf.text = insights.get("title", "Reporte")
    tf.paragraphs[0].font.size = Pt(36)
    tf.paragraphs[0].font.bold = True

    sub = slide.shapes.add_textbox(Inches(0.5), Inches(3.5), Inches(9), Inches(1))
    sf = sub.text_frame
    sf.text = _footer_line(insights)

    if logo and Path(logo).exists():
        slide.shapes.add_picture(str(logo), Inches(0.5), Inches(0.5),
                                 width=Inches(1.5))


def _add_chart_slide(prs: Presentation, title: str, png_bytes: bytes,
                     insights: dict[str, Any]) -> None:
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.6))
    tx.text_frame.text = title
    tx.text_frame.paragraphs[0].font.size = Pt(24)
    tx.text_frame.paragraphs[0].font.bold = True

    # Embed PNG en centro
    import io
    slide.shapes.add_picture(io.BytesIO(png_bytes), Inches(1), Inches(1.2),
                             width=Inches(8))

    _add_footer(slide, insights)


def _add_error_slide(prs: Presentation, title: str, msg: str) -> None:
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    tx = slide.shapes.add_textbox(Inches(0.5), Inches(3), Inches(9), Inches(2))
    tx.text_frame.text = f"{title}\n\n{msg}"
    tx.text_frame.paragraphs[0].font.size = Pt(18)


def _add_insights_slide(prs: Presentation, insights: dict[str, Any]) -> None:
    blank = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank)
    tx = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(9), Inches(0.6))
    tx.text_frame.text = "Insights"
    tx.text_frame.paragraphs[0].font.size = Pt(28)
    tx.text_frame.paragraphs[0].font.bold = True

    body = slide.shapes.add_textbox(Inches(0.7), Inches(1.2), Inches(8.5), Inches(5.5))
    tf = body.text_frame
    tf.word_wrap = True
    items = insights.get("insights", [])
    if not items:
        tf.text = "(Sin insights numerados)"
        return
    for i, ins in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"Insight {ins['number']}: {ins['title']}"
        p.font.size = Pt(14)
        p.font.bold = True
        if ins.get("what"):
            p = tf.add_paragraph()
            p.text = f"  Que: {ins['what']}"
            p.font.size = Pt(12)

    _add_footer(slide, insights)


def _add_footer(slide, insights: dict[str, Any]) -> None:
    fb = slide.shapes.add_textbox(Inches(0.5), Inches(7), Inches(9), Inches(0.3))
    fb.text_frame.text = _footer_line(insights)
    fb.text_frame.paragraphs[0].font.size = Pt(9)


def _footer_line(insights: dict[str, Any]) -> str:
    parts = []
    if insights.get("date"):
        parts.append(insights["date"])
    if insights.get("author"):
        parts.append(insights["author"])
    parts.append("data-analytics-agents · report-export")
    return " · ".join(parts)