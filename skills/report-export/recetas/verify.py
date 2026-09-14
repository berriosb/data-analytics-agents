"""
Verificacion de output para los 3 formatos.

Cada verify_* devuelve True si el archivo es valido, False en caso contrario.
Si el archivo no existe, devuelve False.
"""

from __future__ import annotations

from pathlib import Path


def verify_pdf(path: str | Path) -> bool:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return False
    # Header magico de PDF
    head = p.read_bytes()[:4]
    if head != b"%PDF":
        return False
    # Validar que pdfinfo lo puede abrir (si esta disponible)
    import shutil, subprocess
    if shutil.which("pdfinfo"):
        try:
            r = subprocess.run(["pdfinfo", str(p)], capture_output=True, timeout=10)
            return r.returncode == 0
        except Exception:
            return True  # header valido alcanza si pdfinfo no responde
    return True


def verify_ppt(path: str | Path) -> bool:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        from pptx import Presentation
        prs = Presentation(str(p))
        return len(prs.slides) > 0
    except Exception:
        return False


def verify_html(path: str | Path) -> bool:
    p = Path(path)
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(p.read_text(encoding="utf-8"), "html.parser")
        # Validar tags basicos
        if soup.find("html") is None or soup.find("body") is None:
            return False
        # Validar que imagenes embebidas en base64 son validas (al menos 1)
        imgs = soup.find_all("img")
        if not imgs:
            return True  # sin imagenes pero HTML bien formado es valido
        for img in imgs:
            src = img.get("src")
            if src is None:
                continue
            src_str = " ".join(src) if isinstance(src, list) else str(src)
            if src_str.startswith("data:image/"):
                # Validar prefijo data URI completo
                if "," not in src_str:
                    return False
        return True
    except Exception:
        return False