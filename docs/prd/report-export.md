# PRD — `report-export`

- **Status:** Draft → Ready para implementar tras ADR-001 aceptado
- **Owner:** CodeHak (Bastian)
- **ADR relacionado:** [001-portable-day1](../adr/001-portable-day1.md)
- **Skills relacionadas:** `reporting-analyst` (carga esta al final), `viz-patterns`, `insight-synthesis`

## Goal

Que un data analyst pueda tomar un reporte producido por
`reporting-analyst` (gráficos Plotly + narrativa de `insight-synthesis`)
y exportarlo a **PDF, PPT, o HTML standalone** en un solo comando, listo
para mandar por email/Slack al stakeholder sin que tenga que abrir un
notebook ni correr nada.

## User story

> Como data analyst, terminé un análisis de ventas Q2 2026 con 8 gráficos
> Plotly y 5 insights priorizados. Necesito mandarle al director financiero
> un PDF ejecutivo con los gráficos numerados, los insights como bullets,
> el logo de la empresa, y una portada con fecha y autor. Sin tener que
> tomar screenshots ni pegar imágenes en PowerPoint a mano. Un comando,
> 30 segundos, archivo `reporte_ventas_q2_2026.pdf` listo para enviar.

## Scope in (v1)

- **Tres formatos de export**:
  - **PDF ejecutivo** (vía WeasyPrint con template HTML+CSS, o pdfkit
    como fallback si WeasyPrint falla por dependencias GTK).
  - **PPT nativo** (vía `python-pptx` con cada gráfico en su slide,
    título, insights como bullets, footer con fecha/autor).
  - **HTML standalone** (un solo archivo `.html` con gráficos embebidos
    en base64, sin dependencias externas, abrible en cualquier browser).
- **Templates pre-aprobados**:
  - `executive_pdf.html` — portada + secciones + gráficos numerados +
    insights + footer. CSS limpio, imprimible.
  - `executive_ppt.pptx_template.pptx` — base con slide master configurada.
  - `executive_inline.html` — todo embebido en un solo archivo.
- **Inputs**: recibe un directorio con gráficos Plotly (formato `.html`
  de Plotly o `.png`/`.svg` ya exportados) + un archivo markdown con los
  insights (output de `insight-synthesis`).
- **Metadata**: portada con título, fecha, autor (de env o argumento),
  opcional logo (path a imagen).
- **Numeración**: gráficos numerados `Figura 1, 2, ...`, insights como
  `Insight 1, 2, ...`. Cross-reference en la narrativa.

## Scope out (v1, queda como follow-up)

- **Word/Google Docs**: fuera de scope. Si hay demanda, ADR-002.
- **Reportes interactivos** (con filtros, drill-down): fuera de scope.
  Eso es `stakeholder-comms` app, otra persona.
- **Traducción multi-idioma**: solo español en v1. Multi-idioma es
  follow-up si hay demanda.
- **Branding automático** (colores corporativos): el usuario provee el
  CSS/PPT template. Auto-detectar colores de un logo es follow-up.
- **Envío directo por email/Slack**: la skill exporta el archivo, no lo
  envía. El envío queda al usuario.

## Workflow (las 6 fases de la skill)

1. **Validación de inputs**: recibir directorio con gráficos + archivo
   markdown de insights. Verificar que los archivos existen, los formatos
   son legibles, y el markdown tiene al menos 1 insight. Si falta algo,
   error accionable.
2. **Parsing del markdown de insights**: extraer título, insights
   numerados, fecha/autor del frontmatter YAML. Output como dict.
3. **Render de gráficos**: si los gráficos son `.html` de Plotly, parsear
   el JSON embebido y renderizar a PNG/SVG con kaleido. Si ya son PNG/SVG,
   usar directo.
4. **Construcción del output**:
   - **PDF**: armar HTML con template, pasar por WeasyPrint (o pdfkit
     fallback). Insertar gráficos numerados, insights como bullets,
     footer.
   - **PPT**: clonar template, agregar slide de portada + N slides de
     gráficos (1 gráfico por slide) + slide final de insights.
   - **HTML**: embeber gráficos en base64, CSS inline, archivo único.
5. **Verificación de output**: abrir el archivo resultante y validar:
   - PDF: `pdfinfo` reporta N páginas, sin errores.
   - PPT: `python-pptx` lo reabre sin errores, todas las slides tienen
     al menos un gráfico o bullet.
   - HTML: `BeautifulSoup` parsea sin errores, todas las imágenes
     embebidas son válidas.
6. **Output path**: recibir `--output` o default a
   `./reports/<nombre>.<ext>`. Print del path final + tamaño en MB.

## Recetas iniciales (snippets pre-aprobados)

- `parse_insights_markdown(path) -> dict` — extrae insights del MD.
- `plotly_html_to_png(html_path) -> bytes` — usa kaleido.
- `build_pdf(html_template, insights, charts, output) -> Path`
- `build_ppt(template_path, insights, charts, output) -> Path`
- `build_html(insights, charts, output) -> Path`
- `verify_pdf(path) -> bool`
- `verify_ppt(path) -> bool`
- `verify_html(path) -> bool`

## Templates (referenciados, no hardcodeados en la skill)

- `skills/report-export/templates/executive_pdf.html`
- `skills/report-export/templates/executive_ppt.pptx_template.pptx`
- `skills/report-export/templates/executive_inline.html`
- `skills/report-export/templates/styles.css`

## Verificación (criterios de "listo")

- [ ] Cada formato tiene un ejemplo end-to-end en `examples/`:
  - `examples/report_export_sample/` con gráficos Plotly de muestra +
    insights.md + script que exporta a los 3 formatos.
- [ ] `make test-export-pdf`, `make test-export-ppt`,
  `make test-export-html` ejecutan los ejemplos y validan el output.
- [ ] La skill está en `skills/report-export/SKILL.md` con el template
  de 6 secciones completo.
- [ ] `AGENTS.md` actualizado: `reporting-analyst` carga `report-export`
  AL FINAL, después de `insight-synthesis`.
- [ ] `package.json`: `kaleido`, `python-pptx`, `weasyprint` (con
  fallback documentado) declarados como `peerDependencies` opcionales.
- [ ] `bin/install.js` corre sin cambios.

## Estimación

- Specs + templates HTML/CSS: 1 hora.
- Implementación SKILL.md + recetas + templates: 5-6 horas (la parte
  de PPT y los templates son las más densas).
- Tests de los 3 formatos: 1.5 horas.
- Actualización AGENTS.md/package.json: 30 min.

**Total: ~8-9 horas de código + tests.**