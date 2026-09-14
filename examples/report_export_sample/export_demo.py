"""
Demo end-to-end de `report-export`: genera 3 archivos (PDF, PPT, HTML)
a partir de charts/ + insights.md y los valida con verify_*.

Uso:
    python examples/report_export_sample/export_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Cargar skills via loader (porque report-export tiene guion en el nombre)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from skills_loader import load_skill_packages
load_skill_packages("skills")

from report_export.recetas import (
    parse_insights_markdown, build_pdf, build_ppt, build_html,
    verify_pdf, verify_ppt, verify_html,
)

EXAMPLE_DIR = Path(__file__).parent
CHARTS_DIR = EXAMPLE_DIR / "charts"
INSIGHTS_MD = EXAMPLE_DIR / "insights.md"
TEMPLATES = EXAMPLE_DIR.parents[1] / "skills" / "report-export" / "templates"
OUT_DIR = EXAMPLE_DIR / "out"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    insights = parse_insights_markdown(INSIGHTS_MD)
    charts = sorted(CHARTS_DIR.glob("*.png"))
    print(f"Insights: {len(insights['insights'])} numerados")
    print(f"Graficos: {len(charts)} PNGs")

    # PDF
    pdf_path = OUT_DIR / "reporte_h1_2026.pdf"
    print(f"\n[1/3] PDF -> {pdf_path.name}")
    try:
        build_pdf(insights, charts, TEMPLATES, pdf_path)
        ok = verify_pdf(pdf_path)
        print(f"     verify_pdf: {'OK' if ok else 'FAIL'} ({pdf_path.stat().st_size} bytes)")
    except Exception as e:
        print(f"     FAIL: {e}")
        raise

    # PPT
    ppt_path = OUT_DIR / "reporte_h1_2026.pptx"
    print(f"\n[2/3] PPT -> {ppt_path.name}")
    try:
        build_ppt(insights, charts, None, ppt_path)
        ok = verify_ppt(ppt_path)
        print(f"     verify_ppt: {'OK' if ok else 'FAIL'} ({ppt_path.stat().st_size} bytes)")
    except Exception as e:
        print(f"     FAIL: {e}")
        raise

    # HTML
    html_path = OUT_DIR / "reporte_h1_2026.html"
    print(f"\n[3/3] HTML -> {html_path.name}")
    try:
        build_html(insights, charts, TEMPLATES, html_path)
        ok = verify_html(html_path)
        print(f"     verify_html: {'OK' if ok else 'FAIL'} ({html_path.stat().st_size} bytes)")
    except Exception as e:
        print(f"     FAIL: {e}")
        raise

    print("\nOK: los 3 formatos se exportaron y validaron.")


if __name__ == "__main__":
    main()