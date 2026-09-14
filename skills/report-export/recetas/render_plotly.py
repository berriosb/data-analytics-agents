"""
Render de graficos Plotly a PNG.

Soporta tres formatos de entrada:
- `.html` (Plotly standalone con JSON embebido) → parsea y exporta a PNG con kaleido
- `.png` → copia el archivo al destino
- `.svg` → copia el archivo al destino

Las funciones devuelven SIEMPRE PNG bytes (para PDF/HTML embed) o paths (para PPT).
"""

from __future__ import annotations

import json
import re
from pathlib import Path


_PLYO_HTML_RE = re.compile(
    r"Plotly\.newPlot\((.*?)\)\s*;?\s*</script>", re.DOTALL
)


def collect_charts(charts_dir: str | Path) -> list[Path]:
    """Devuelve la lista ordenada de graficos encontrados en el directorio.

    Orden: numerico por sufijo `figura_01.png`, `figura_2.svg`, etc.
    Si el nombre no tiene numero, va al final en orden alfabetico.
    Solo extensiones: .png, .svg, .html.
    """
    p = Path(charts_dir)
    if not p.exists() or not p.is_dir():
        raise FileNotFoundError(
            f"No existe el directorio de graficos: {charts_dir}. "
            "Pasale la ruta al directorio donde estan los PNG/SVG/HTML de Plotly."
        )
    files = [f for f in p.iterdir()
             if f.is_file() and f.suffix.lower() in (".png", ".svg", ".html")]

    def sort_key(f: Path):
        nums = re.findall(r"\d+", f.stem)
        n = int(nums[-1]) if nums else 999
        return (n, f.name)

    return sorted(files, key=sort_key)


def plotly_html_to_png(html_path: str | Path) -> bytes:
    """Lee un HTML Plotly standalone y exporta a PNG bytes via kaleido.

    Estrategia:
    1. Extrae la llamada `Plotly.newPlot(...)` del <script>
    2. Parsea el primer argumento (el dict de datos + layout) como JSON
    3. Reconstruye un `go.Figure` y exporta con `fig.to_image(format='png')`

    Si el HTML no contiene Plotly (e.g. es HTML plano), lanza error accionable.
    """
    text = Path(html_path).read_text(encoding="utf-8")
    m = _PLYO_HTML_RE.search(text)
    if not m:
        raise ValueError(
            f"El HTML {html_path} no contiene un bloque Plotly.newPlot(...). "
            "Exporta el grafico desde Plotly como HTML standalone o como PNG directo."
        )
    # Extraer el primer argumento (fig dict). El match captura "(...)" con
    # `Plotly.newPlot('div', [{...}], {...})` o variantes.
    inside = m.group(1)
    # Cortar hasta la primera `,` que separa el nombre del div de los datos
    depth = 0
    end = -1
    for i, ch in enumerate(inside):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            end = i
            break
    if end < 0:
        raise ValueError(f"No pude parsear el bloque Plotly de {html_path}.")
    after_div = inside[end + 1:].lstrip()
    # Despues del div viene o bien `[{...}], {...}` o `[...]`
    # Necesitamos los primeros 2 argumentos completos. Cortamos en el siguiente
    # separador de argumentos a depth==0.
    args = _split_top_level_args(after_div)
    if len(args) < 1:
        raise ValueError(f"No encontre data dict en {html_path}.")
    data = json.loads(args[0])
    layout = json.loads(args[1]) if len(args) > 1 else {}

    import plotly.graph_objects as go
    fig = go.Figure(data=data, layout=layout)

    try:
        png = fig.to_image(format="png", width=1200, height=700)
    except Exception as e:
        raise RuntimeError(
            f"kaleido fallo exportando {html_path} a PNG: {e}. "
            "Verifica que kaleido este instalado: pip install kaleido"
        ) from e
    return png


def _split_top_level_args(s: str) -> list[str]:
    """Divide argumentos top-level por `,` respetando brackets."""
    args: list[str] = []
    depth = 0
    in_str = None
    buf: list[str] = []
    for ch in s:
        if in_str:
            buf.append(ch)
            if ch == in_str and (not buf or buf[-2] != "\\"):
                in_str = None
            continue
        if ch in "\"'`":
            in_str = ch
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
            buf.append(ch)
        elif ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        args.append("".join(buf).strip())
    return args


def chart_to_png_bytes(chart: Path) -> bytes:
    """Convierte cualquier formato soportado a PNG bytes.

    PNG: lo lee tal cual.
    SVG: lo lee tal cual (los formatos PDF/HTML aceptan SVG embebido via <img>).
    HTML: lo parsea con plotly_html_to_png.
    """
    suffix = chart.suffix.lower()
    if suffix == ".png":
        return chart.read_bytes()
    if suffix == ".svg":
        return chart.read_bytes()
    if suffix == ".html":
        return plotly_html_to_png(chart)
    raise ValueError(f"Formato de grafico no soportado: {chart.suffix}")