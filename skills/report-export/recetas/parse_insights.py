"""
Parser del markdown de insights (output de `insight-synthesis` skill).

Extrae:
- title (frontmatter `title:` o primer H1)
- date (frontmatter `date:` o `YYYY-MM-DD`)
- author (frontmatter `author:`)
- insights: lista de dicts con `number`, `title`, `what`, `why`, `now`
- summary (opcional, primer parrafo despues del H1)

Si el MD no tiene insights numerados, devuelve lista vacia y deja que la
skill principal lance el error accionable.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_INSIGHT_HEADER_RE = re.compile(
    r"^#{1,3}\s+(?:Insight\s+)?(\d+)[:.\s]+(.+?)\s*$", re.MULTILINE
)


def parse_insights_markdown(path: str | Path) -> dict[str, Any]:
    """Parsea el MD de insights y devuelve un dict normalizado.

    Returns:
        {
            "title": str,
            "date": str,            # YYYY-MM-DD o vacio
            "author": str,          # o vacio
            "summary": str,         # parrafo introductorio o vacio
            "insights": [            # lista vacia si no hay insights numerados
                {"number": int, "title": str, "what": str,
                 "why": str, "now": str}
            ],
        }
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"No existe el archivo de insights: {p}. "
            "Verifica que el output de insight-synthesis apunte a un .md valido."
        )
    text = p.read_text(encoding="utf-8")

    fm: dict[str, str] = {}
    m = _FRONTMATTER_RE.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                fm[k.strip()] = v.strip()
        text = text[m.end():]

    title = _extract_title(text, fm)
    summary = _extract_summary(text)
    insights = _extract_insights(text)

    return {
        "title": title,
        "date": fm.get("date", ""),
        "author": fm.get("author", ""),
        "summary": summary,
        "insights": insights,
    }


def _extract_title(text: str, fm: dict[str, str]) -> str:
    if "title" in fm:
        return fm["title"]
    m = re.search(r"^#\s+(.+?)\s*$", text, re.MULTILINE)
    return m.group(1).strip() if m else "Reporte"


def _extract_summary(text: str) -> str:
    """Primer parrafo no-vacio despues del H1 y antes del primer insight."""
    lines = text.splitlines()
    started = False
    buf: list[str] = []
    for line in lines:
        s = line.strip()
        if not started:
            if s.startswith("#"):
                started = True
                continue
            continue
        if not s:
            if buf:
                break
            continue
        if _INSIGHT_HEADER_RE.match(s):
            break
        buf.append(s)
    return " ".join(buf).strip()


def _extract_insights(text: str) -> list[dict[str, Any]]:
    """Encuentra bloques `## Insight N: Title` y extrae What/Why/Now si existen."""
    insights: list[dict[str, Any]] = []
    matches = list(_INSIGHT_HEADER_RE.finditer(text))
    for i, m in enumerate(matches):
        number = int(m.group(1))
        title = m.group(2).strip()
        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[block_start:block_end].strip()
        what, why, now = _split_what_why_now(block)
        insights.append({
            "number": number,
            "title": title,
            "what": what,
            "why": why,
            "now": now,
        })
    return insights


def _split_what_why_now(block: str) -> tuple[str, str, str]:
    """Si el bloque tiene subsecciones **Que** / **Por que** / **Ahora que**, las
    devuelve por separado. Si no, devuelve todo el bloque en `what`.
    """
    sections = {"what": "", "why": "", "now": ""}
    current = None
    for line in block.splitlines():
        s = line.strip()
        h = re.match(r"^\*\*(Qué|Que|Por qué|Por que|Ahora qué|Ahora que)\*\*\s*:?\s*(.*)$",
                     s, re.IGNORECASE)
        if h:
            label = h.group(1).lower()
            if label.startswith("qu"):
                current = "what"
                sections[current] = h.group(2).strip()
            elif label.startswith("por"):
                current = "why"
                sections[current] = h.group(2).strip()
            elif label.startswith("aho"):
                current = "now"
                sections[current] = h.group(2).strip()
        elif current and s:
            sections[current] = (sections[current] + " " + s).strip()

    if not any(sections.values()):
        sections["what"] = block.strip()
    return sections["what"], sections["why"], sections["now"]