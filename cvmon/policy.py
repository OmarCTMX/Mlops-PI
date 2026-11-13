"""Política de confianza de dos umbrales y tres zonas (R3).

Interpretación:
    s >= superior            -> accepted  (aceptada por política; NO implica acierto)
    inferior <= s < superior -> doubt     (duda)
    s < inferior             -> low       (baja confianza)

Fallos de inferencia, entradas inválidas y ausencia de puntuación son ESTADOS aparte, no zonas.
"""
from __future__ import annotations

import math

from .config import validate_thresholds

ZONE_ACCEPTED = "accepted"
ZONE_DOUBT = "doubt"
ZONE_LOW = "low"
ZONES = (ZONE_ACCEPTED, ZONE_DOUBT, ZONE_LOW)

STATUS_OK = "ok"
STATUS_INFERENCE_ERROR = "inference_error"
STATUS_INVALID_INPUT = "invalid_input"
STATUSES = (STATUS_OK, STATUS_INFERENCE_ERROR, STATUS_INVALID_INPUT)


def classify_zone(score: float | None, lower: float, upper: float) -> str | None:
    """Devuelve la zona de una puntuación o None si no hay puntuación válida."""
    validate_thresholds(lower, upper)
    if score is None or isinstance(score, bool) or not isinstance(score, (int, float)):
        return None
    if math.isnan(score) or math.isinf(score) or score < 0.0 or score > 1.0:
        return None
    if score >= upper:
        return ZONE_ACCEPTED
    if score >= lower:
        return ZONE_DOUBT
    return ZONE_LOW
