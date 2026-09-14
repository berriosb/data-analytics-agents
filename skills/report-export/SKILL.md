---
name: report-export
description: Exporta un reporte ejecutivo (graficos Plotly + insights en markdown) a PDF, PPTX o HTML standalone en un solo comando. Usese al final del flujo de `reporting-analyst` despues de `insight-synthesis` para entregar al stakeholder sin que tenga que abrir un notebook ni correr nada. Acepta directorio con graficos PNG/SVG/HTML de Plotly + un .md de insights con frontmatter YAML y secciones `## Insight N: title` (con sub-bloques opcionales **Qué**/**Por qué**/**Ahora qué**). Output: PDF (WeasyPrint, fallback pdfkit), PPTX nativo (python-pptx), o HTML autocontenido con imagenes en base64.
---

# Report Export

Exporta el output combinado de `viz-patterns` (graficos Plotly) + `insight-synthesis`
(markdown con insights numerados) a uno de tres formatos presentables.

## Descripcion general

A diferencia de las demas skills (que viven en el flujo de trabajo), esta
opera **al final del pipeline** como servicio de empaquetado. Recibe dos
inputs:

- Un directorio con graficos (`.png`, `.svg`, o `.html` standalone de Plotly)
- Un markdown de insights con frontmatter YAML (`title`, `date`, `author`)
  y secciones `## Insight N: <titulo>` (con sub-bloques opcionales
  `**Qué**`, `**Por qué**`, `**Ahora qué**`)

Y produce:

- **PDF** ejecutivo (WeasyPrint; fallback a pdfkit si WeasyPrint falla por
  dependencias GTK en Linux). Recomendado para email al director financiero.
- **PPTX** nativo (python-pptx). Recomendado para presentar en reunion.
- **HTML** standalone con graficos embebidos en base64. Recomendado para
  Slack/Teams (un solo archivo, sin dependencias).

## Cuando usar

Invocar esta skill cuando el pedido matchee con alguno de:

- "Tengo 8 graficos Plotly y 5 insights en MD, mandame un PDF."
- "Exporta el reporte a PowerPoint para la reunion del viernes."
- "Necesito un HTML que pueda mandar por Slack."
- "Quiero mandar el reporte al director sin que tenga que correr nada."

**No** invocar cuando:

- El usuario todavia esta explorando datos → seguir en `reporting-analyst`.
- No hay insights escritos todavia → terminar `insight-synthesis` primero.
- Solo quiere guardar graficos individuales → `viz-patterns` (sin export).
- Necesita un reporte interactivo con filtros/drill-down → fuera de scope v1.

## Flujo de trabajo

1. **Validar inputs**: recibir `--charts-dir`, `--insights`, `--format`,
   `--output`, `--logo` (opcional). Verificar que existen, que `--format`
   es uno de `pdf|pptx|html`, y que `--insights` parsea a un dict con
   al menos 1 insight numerado. Si falta algo, error accionable.
2. **Parsear el markdown de insights** con `parse_insights_markdown(path)`
   → devuelve dict con `title`, `date`, `author`, `summary`, `insights[]`.
3. **Recolectar graficos** del directorio con `collect_charts(dir)` (orden
   numerico por sufijo `figura_01.png`; alfabetico al final si no hay
   numero).
4. **Renderizar graficos** (si son HTML de Plotly) con `plotly_html_to_png`
   que parsea el JSON embebido y exporta con kaleido. PNG/SVG pasan tal cual.
5. **Construir el output** segun formato:
   - `build_pdf(insights, charts, template_dir, output, logo)` →
     WeasyPrint; si falla, pdfkit (requiere `wkhtmltopdf` binario).
   - `build_ppt(insights, charts, template_path, output, logo)` →
     python-pptx; template opcional.
   - `build_html(insights, charts, template_dir, output, logo)` →
     archivo unico con base64 embebido.
6. **Verificar** el output con `verify_pdf` / `verify_ppt` / `verify_html`
   (header magico, parseo, presencia de slides/imgs).
7. **Reportar** el path final + tamano en MB al usuario.

## Recetas pre-aprobadas (importables)

```python
import sys
sys.path.insert(0, "ruta/al/repo")
from skills_loader import load_skill_packages
load_skill_packages("skills")

from report_export.recetas import (
    parse_insights_markdown,  # MD -> dict
    collect_charts,           # dir -> [Path]
    plotly_html_to_png,       # HTML Plotly -> PNG bytes
    build_pdf, build_ppt, build_html,
    verify_pdf, verify_ppt, verify_html,
)
```

Las recetas viven en `skills/report-export/recetas/` y son funciones puras
con paths validados. NO contienen `eval()`, NO escriben sobre archivos del
usuario sin `--output` explicito, NO aceptan codigo del usuario.

## CLI rapido (uso desde el agente o terminal)

```bash
# Generar sample primero
python examples/report_export_sample/generate_sample.py

# Exportar los 3 formatos
python examples/report_export_sample/export_demo.py

# O usar las recetas ad-hoc:
python -c "
import sys; sys.path.insert(0, '.')
from skills_loader import load_skill_packages
load_skill_packages('skills')
from report_export.recetas import parse_insights_markdown, build_pdf
from pathlib import Path
insights = parse_insights_markdown('examples/report_export_sample/insights.md')
charts = sorted(Path('examples/report_export_sample/charts').glob('*.png'))
templates = Path('skills/report-export/templates')
out = build_pdf(insights, charts, templates, 'reports/reporte.pdf')
print('PDF:', out, out.stat().st_size, 'bytes')
"
```

## Templates

Viven en `skills/report-export/templates/` (referenciados, no hardcodeados
en la skill):

- `executive_pdf.html` — Jinja-style para PDF (gradiente oscuro en portada)
- `executive_inline.html` — para HTML standalone (mismo look)
- `styles.css` — CSS limpio imprimible, paleta neutra profesional

Los templates usan placeholders `{{title}}`, `{{date}}`, `{{author}}`,
`{{summary_html}}`, `{{insights_html}}`, `{{charts_html}}`,
`{{logo_data_uri}}`. Para customizar el look corporativo, edita el CSS o
duplica los templates y pasa tu propia `template_dir` a las recetas.

## Justificaciones comunes

- **Por que WeasyPrint en vez de ReportLab directo?** WeasyPrint acepta
  HTML+CSS (mas facil de customizar que coordenadas absolutas) y produce
  PDFs bien maquetados con `@media print`. ReportLab es para reportes
  pixel-perfect (overkill para v1).
- **Por que python-pptx en vez de LibreOffice headless?** python-pptx
  produce PPTX nativo editable; LibreOffice requiere conversion. Si el
  stakeholder edita el PPT, python-pptx gana.
- **Por que HTML con base64?** Porque el stakeholder recibe UN archivo y
  puede abrirlo offline sin paths rotos.
- **Por que el guion en el nombre del skill (`report-export`)?** Porque
  asi se lee como un nombre humano en la doc. Para imports Python se usa
  el loader `skills_loader.py` que lo expone como `report_export`.

## Senales de alerta

- WeasyPrint falla con `cannot load library 'libgobject-2.0-0'` en
  Linux → el usuario no tiene GTK. Mostrar el mensaje accionable de
  `build_pdf` (instalar `libpango-1.0-0` o `wkhtmltopdf`).
- kaleido no esta instalado y el usuario pasa HTML de Plotly →
  `plotly_html_to_png` levanta error claro. Sugerir `pip install kaleido`
  o exportar los graficos como PNG directo desde el notebook.
- El markdown no tiene insights numerados → la skill emite warning y
  produce un PDF/PPT/HTML con la seccion "Sin insights numerados".
  Es intencional: el usuario puede haber pasado un MD resumen sin insights.
- El directorio de graficos esta vacio → mismo warning.
- El usuario pide branding automatico desde un logo → fuera de scope v1
  (el usuario provee el CSS/PPT template).

## Verificacion

Criterios de "listo" (ver `docs/prd/report-export.md`):

- [x] Cada formato tiene un ejemplo end-to-end en
      `examples/report_export_sample/`.
- [x] `make test-export-pdf`, `make test-export-ppt`,
      `make test-export-html` ejecutan los ejemplos y validan el output.
- [x] La skill esta en `skills/report-export/SKILL.md` con el template
      de 6 secciones completo.
- [x] `AGENTS.md` actualizado: `reporting-analyst` carga `report-export`
      AL FINAL, despues de `insight-synthesis`.
- [x] `package.json`: `kaleido`, `python-pptx`, `weasyprint` declarados
      como `peerDependencies` opcionales con fallback documentado.

## Dependencias

- **kaleido** (obligatoria para HTML Plotly) — peerDep opcional
- **python-pptx** (obligatoria para PPT) — peerDep opcional
- **weasyprint** (obligatoria para PDF) — peerDep opcional
- **pdfkit** + binario `wkhtmltopdf` (fallback para PDF) — opcional
- **beautifulsoup4** (para verificar HTML) — peerDep opcional
- **jinja2** no se usa; las plantillas son string-substitution simple.

Si una dep cloud esta, el agente debe decir `pip install <dep>` al usuario,
NO instalarla automaticamente.