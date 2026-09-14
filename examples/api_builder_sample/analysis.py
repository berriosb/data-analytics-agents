"""
Funcion de scoring de muestra para probar api-builder.

Esta funcion es el 'analisis terminado' del data analyst. La skill
api-builder toma este archivo + nombre de funcion y genera una API REST
production-ready (FastAPI + Dockerfile + tests).
"""

from __future__ import annotations

from typing import Optional


def score_cliente(
    monto_mensual: float,
    antiguedad_meses: int,
    segmento: str = "SMB",
    tiene_garante: bool = False,
) -> dict:
    """Score de credito 0-1000 para un cliente del banco.

    Args:
        monto_mensual: ingreso mensual declarado del cliente en CLP.
        antiguedad_meses: meses como cliente del banco.
        segmento: SMB | Mid-market | Enterprise.
        tiene_garante: True si tiene garante solidario.

    Returns:
        Dict con score (0-1000), nivel (Bajo/Medio/Alto), y recomendacion.
    """
    base = min(500, monto_mensual / 1000)          # cap 500
    base += min(200, antiguedad_meses * 2)         # cap 200
    if segmento == "Enterprise":
        base += 150
    elif segmento == "Mid-market":
        base += 80
    if tiene_garante:
        base += 100
    score = int(min(1000, max(0, base)))

    if score < 400:
        nivel, rec = "Bajo", "Rechazar o pedir garantias adicionales"
    elif score < 700:
        nivel, rec = "Medio", "Aprobar con monitoring trimestral"
    else:
        nivel, rec = "Alto", "Aprobar con linea estandar"

    return {
        "score": score,
        "nivel": nivel,
        "recomendacion": rec,
        "inputs": {
            "monto_mensual": monto_mensual,
            "antiguedad_meses": antiguedad_meses,
            "segmento": segmento,
            "tiene_garante": tiene_garante,
        },
    }