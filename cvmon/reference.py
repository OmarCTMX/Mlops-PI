"""Referencia de confianza (R3.1, R3.3) construida con inferencias reales del escenario REF."""
from __future__ import annotations

import json
import math
import sqlite3
import time
from pathlib import Path
from typing import Any

from .db import utc_iso

BINS = 10


class ReferenceError(RuntimeError):
    pass


def _q(sorted_vals: list[float], q: float) -> float:
    pos = (len(sorted_vals) - 1) * q / 100.0
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_vals[lo] if lo == hi else sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def build_reference(conn: sqlite3.Connection, run_ids: list[str], out_path: str | Path) -> dict[str, Any]:
    if not run_ids:
        raise ReferenceError("Se requiere al menos un run de referencia")
    runs = [dict(r) for r in conn.execute(
        f"SELECT * FROM runs WHERE run_id IN ({','.join('?' for _ in run_ids)})", run_ids)]
    if len(runs) != len(set(run_ids)):
        raise ReferenceError("Algún run indicado no existe")
    # Misma identidad de modelo (y por tanto de preprocesamiento) para que la comparación sea válida
    ident = {(r["model_id"], r["model_version"], r["model_sha256"]) for r in runs}
    if len(ident) != 1:
        raise ReferenceError(f"Los runs de referencia mezclan modelos/versiones: {ident}")
    confs = [r["confidence"] for r in conn.execute(
        f"SELECT confidence FROM events WHERE status='ok' AND confidence IS NOT NULL "
        f"AND run_id IN ({','.join('?' for _ in run_ids)})", run_ids)]
    if not confs:
        raise ReferenceError("Los runs no contienen inferencias con puntuación")
    s = sorted(confs)
    n = len(s)
    mean = sum(s) / n
    std = math.sqrt(sum((x - mean) ** 2 for x in s) / n)
    edges = [i / BINS for i in range(BINS + 1)]
    counts = [0] * BINS
    for v in s:
        counts[min(int(v * BINS), BINS - 1)] += 1
    ref = {
        "built_at": utc_iso(time.time()),
        "run_ids": run_ids,
        "n": n,
        "mean": mean,
        "std": std,
        "min": s[0],
        "max": s[-1],
        "percentiles": {f"p{p:02d}": _q(s, p) for p in (5, 10, 25, 50, 75, 90, 95)},
        "hist_edges": edges,
        "hist_counts": counts,
        "hist_props": [c / n for c in counts],
        "model": {"model_id": runs[0]["model_id"], "version": runs[0]["model_version"],
                  "sha256": runs[0]["model_sha256"]},
        "config_hashes": sorted({r["config_hash"] for r in runs}),
        "git_commits": sorted({r["git_commit"] for r in runs if r["git_commit"]}),
        "note": "Distribución de confianza top-1 en condiciones de referencia (escena esperada). "
                "La confianza es una puntuación de salida, no probabilidad de acierto.",
    }
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ref, indent=2, ensure_ascii=False), encoding="utf-8")
    return ref


def suggest_thresholds(ref: dict[str, Any]) -> tuple[float, float]:
    """Regla documentada: superior = P25 y inferior = P05 de la referencia, redondeados a 0.05 hacia abajo."""
    def floor05(x: float) -> float:
        return max(0.0, math.floor(x / 0.05 + 1e-9) * 0.05)

    upper = round(floor05(ref["percentiles"]["p25"]), 2)
    lower = round(floor05(ref["percentiles"]["p05"]), 2)
    if lower >= upper:
        lower = round(max(0.0, upper - 0.05), 2)
    return lower, upper


def justification_markdown(ref: dict[str, Any], lower: float, upper: float, conn: sqlite3.Connection | None = None) -> str:
    p = ref["percentiles"]
    sl, su = suggest_thresholds(ref)
    lines = [
        "# Justificación de umbrales (R3.1)",
        "",
        f"- Modelo: `{ref['model']['model_id']}` versión `{ref['model']['version']}` (sha256 `{ref['model']['sha256'][:12]}…`)",
        f"- Observaciones de referencia: n = {ref['n']} (runs: {', '.join(ref['run_ids'])})",
        f"- Construida: {ref['built_at']}",
        "",
        "## Distribución de confianza top-1 en condiciones de referencia",
        "",
        "| Estadístico | Valor |", "| --- | --- |",
        f"| media | {ref['mean']:.4f} |", f"| desviación estándar | {ref['std']:.4f} |",
        f"| mínimo / máximo | {ref['min']:.4f} / {ref['max']:.4f} |",
    ]
    for k, v in p.items():
        lines.append(f"| {k.upper()} | {v:.4f} |")
    lines += ["", "## Regla de elección", "",
              "- Umbral superior = P25 de la referencia (redondeado hacia abajo a múltiplos de 0.05): "
              "se espera que ~75 % de las observaciones normales queden aceptadas.",
              "- Umbral inferior = P05 de la referencia (redondeado hacia abajo): solo ~5 % de las observaciones "
              "normales deberían caer en baja confianza, de modo que una proporción alta sea señal de cambio.",
              f"- Valores que produce la regla con esta referencia: inferior = {sl:.2f}, superior = {su:.2f}.",
              f"- **Valores configurados**: inferior = {lower:.2f}, superior = {upper:.2f} "
              f"({'coinciden con la regla' if (abs(lower - sl) < 1e-9 and abs(upper - su) < 1e-9) else 'difieren de la regla; ver nota'}).",
              "", "## Reparto de la referencia con los umbrales configurados", "",
              "| Zona | Condición | Observaciones | Proporción |", "| --- | --- | --- | --- |"]
    if conn is not None:
        ph = ",".join("?" for _ in ref["run_ids"])
        confs = [r["confidence"] for r in conn.execute(
            f"SELECT confidence FROM events WHERE status='ok' AND confidence IS NOT NULL AND run_id IN ({ph})",
            ref["run_ids"])]
        n = len(confs)
        acc = sum(1 for c in confs if c >= upper)
        dou = sum(1 for c in confs if lower <= c < upper)
        low = sum(1 for c in confs if c < lower)
        for name, cond, k in (("accepted", f"s >= {upper:.2f}", acc), ("doubt", f"{lower:.2f} <= s < {upper:.2f}", dou),
                              ("low", f"s < {lower:.2f}", low)):
            lines.append(f"| {name} | {cond} | {k} | {k / n:.3f} |" if n else f"| {name} | {cond} | 0 | - |")
    lines += ["", "## Límites", "",
              "- La confianza es la probabilidad softmax de la clase top-1; no es probabilidad de acierto ni se "
              "calibró formalmente (no se exige).",
              "- La referencia corresponde a UNA escena/cámara/iluminación; si cambian modelo, preprocesamiento o "
              "configuración, las series deben separarse y la referencia reconstruirse.",
              "- Los umbrales se fijan antes de ejecutar C1 y C2 y no se modifican para aprobar escenarios."]
    return "\n".join(lines) + "\n"
