"""
Genera un sample completo para probar `report-export`:
- 3 graficos Plotly (PNG via kaleido) en examples/report_export_sample/charts/
- 1 markdown de insights en examples/report_export_sample/insights.md
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px


EXAMPLE_DIR = Path(__file__).parent
CHARTS_DIR = EXAMPLE_DIR / "charts"


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({
        "month": ["Ene", "Feb", "Mar", "Abr", "May", "Jun"] * 2,
        "region": ["Norte"] * 6 + ["Sur"] * 6,
        "revenue": [120, 145, 160, 180, 210, 230, 80, 95, 110, 130, 150, 165],
    })

    fig1 = px.line(df, x="month", y="revenue", color="region",
                   title="Figura 1: Revenue mensual por region Q1-Q2 2026")
    fig1.write_image(str(CHARTS_DIR / "figura_1_revenue_lineal.png"))

    fig2 = px.bar(df.groupby("region", as_index=False).revenue.sum(),
                  x="region", y="revenue",
                  title="Figura 2: Revenue total por region H1 2026")
    fig2.write_image(str(CHARTS_DIR / "figura_2_revenue_barras.png"))

    seg = pd.DataFrame({
        "segmento": ["Enterprise", "Mid-market", "SMB"],
        "clientes": [12, 45, 180],
    })
    fig3 = px.pie(seg, names="segmento", values="clientes",
                  title="Figura 3: Distribucion de clientes por segmento")
    fig3.write_image(str(CHARTS_DIR / "figura_3_segmento_pie.png"))

    md = EXAMPLE_DIR / "insights.md"
    md.write_text("""---
title: "Reporte ejecutivo H1 2026 — Revenue & Clientes"
date: 2026-07-01
author: "Bastian Berrios"
---

Resumen del primer semestre: revenue consolidado crecio 18% YoY, con el segmento
Enterprise liderando el crecimiento. Norte mostro una aceleracion sostenida desde
marzo mientras que Sur se mantuvo estable.

## Insight 1: Norte despegó en Q2

**Qué:** Revenue de Norte crecio 35% entre marzo y junio.
**Por qué:** Captura de 3 cuentas Enterprise en abril.
**Ahora qué:** Priorizar expansion a cuentas similares en Q3.

## Insight 2: Enterprise representa el 60% del revenue total

**Qué:** 12 clientes Enterprise aportan el 60% del revenue H1.
**Por qué:** Ticket promedio 4x mayor que SMB.
**Ahora qué:** Programa de customer success dedicado a top 20 cuentas.

## Insight 3: Sur se estancó

**Qué:** Revenue de Sur crecio solo 4% en H1 vs 35% de Norte.
**Por qué:** Sin nuevas cuentas capturadas desde febrero.
**Ahora qué:** Renovar equipo comercial sur + plan agresivo Q3-Q4.
""", encoding="utf-8")

    print(f"OK: 3 PNGs en {CHARTS_DIR}/ + insights.md")


if __name__ == "__main__":
    main()