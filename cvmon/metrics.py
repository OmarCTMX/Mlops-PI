"""Métricas del sistema (R2). Cada métrica se calcula a partir de observaciones primarias en SQLite.

Convenciones comunes (M1/M3):
  * Población: todas las observaciones del run indicado, hasta el instante de referencia T.
  * Cero observaciones -> value = None (NULL) y detail.reason = 'sin_observaciones'. Nunca 0 ni 1.
  * Percentiles: interpolación lineal entre rangos (pos = (n-1)*q), igual que numpy 'linear'.
  * Tiempos en milisegundos (ms) salvo indicación. Epoch en segundos UTC.
La verificación independiente (M5) está en cvmon/recalc.py, que NO reutiliza este módulo.
"""
from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

from . import db

# ---- Catálogo: metric_id -> (grupo, tipo, descripción corta)
BASE_METRICS = {
    "G1_inference_ms_p95": ("G1", "Tiempo de inferencia p50/p95 (ms)"),
    "G2_processing_fps": ("G2", "FPS de procesamiento (frames inferidos por segundo)"),
    "G3_process_rss_mb": ("G3", "RAM (RSS) del proceso de inferencia, media (MB)"),
    "G4_low_conf_share": ("G4", "Proporción de baja confianza"),
    "G5_trace_coverage": ("G5", "Cobertura de trazabilidad de eventos"),
    "G6_version_match_share": ("G6", "Versión esperada frente a reportada"),
    "G7_active_alerts": ("G7", "Alertas activas en el instante T"),
}
EXTRA_METRICS = {
    "X1_capture_fps": ("G2", "FPS de captura"),
    "X2_dropped_share": ("G2", "Proporción de frames descartados por la aplicación (por motivo)"),
    "X3_process_cpu_pct": ("G3", "CPU del proceso (media, % de un núcleo)"),
    "X4_e2e_ms_p95": ("G2", "Latencia de extremo a extremo p95 con desglose de etapas (ms)"),
    "X5_confidence_psi": ("G4", "PSI de la distribución de confianza frente a la referencia"),
    "X6_invalid_input_rate": ("G5", "Tasa de entradas inválidas"),
}

REQUIRED_EVENT_FIELDS = (
    "event_id", "run_id", "frame_id", "task", "captured_at", "source_id", "model_id", "model_version",
    "config_hash", "status", "threshold_lower", "threshold_upper",
)


def percentile(values: list[float], q: float) -> float | None:
    """Percentil q en [0,100] con interpolación lineal."""
    if not values:
        return None
    s = sorted(values)
    pos = (len(s) - 1) * q / 100.0
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(s[int(pos)])
    return float(s[lo] + (s[hi] - s[lo]) * (pos - lo))


def _res(metric_id, value, n, detail=None, T=None):
    grp = (BASE_METRICS.get(metric_id) or EXTRA_METRICS[metric_id])[0]
    d = dict(detail or {})
    if value is None and "reason" not in d:
        d["reason"] = "sin_observaciones"
    return {"metric_id": metric_id, "grp": grp, "value": value, "n": n, "detail": d, "ts": T}


def psi(expected: list[float], actual: list[float], eps: float = 1e-4) -> float:
    total = 0.0
    for e, a in zip(expected, actual):
        e = max(e, eps)
        a = max(a, eps)
        total += (a - e) * math.log(a / e)
    return total


def histogram_props(values: list[float], edges: list[float]) -> list[float]:
    counts = [0] * (len(edges) - 1)
    for v in values:
        for i in range(len(counts)):
            last = i == len(counts) - 1
            if edges[i] <= v < edges[i + 1] or (last and v == edges[-1]):
                counts[i] += 1
                break
    n = sum(counts)
    return [c / n for c in counts] if n else [0.0] * len(counts)


def reference_time(conn: sqlite3.Connection, run_id: str) -> float:
    r = conn.execute("SELECT MAX(processed_epoch) m FROM events WHERE run_id=?", (run_id,)).fetchone()
    run = conn.execute("SELECT started_epoch, ended_epoch FROM runs WHERE run_id=?", (run_id,)).fetchone()
    cands = [x for x in (r["m"], run["ended_epoch"] if run else None) if x is not None]
    return max(cands) if cands else (run["started_epoch"] if run else 0.0)


def compute_all(
    conn: sqlite3.Connection,
    run_id: str,
    data_dir: str | Path,
    reference: dict[str, Any] | None = None,
    T: float | None = None,
    min_psi_samples: int = 30,
) -> list[dict[str, Any]]:
    if T is None:
        T = reference_time(conn, run_id)
    data_dir = Path(data_dir)
    ev = db.query(conn, "SELECT * FROM events WHERE run_id=? AND processed_epoch<=? ORDER BY seq", (run_id, T))
    ok = [e for e in ev if e["status"] == "ok"]
    out: list[dict[str, Any]] = []

    # ---- G1 tiempo de inferencia p50/p95
    times = [e["inference_ms"] for e in ok if e["inference_ms"] is not None]
    out.append(_res("G1_inference_ms_p95", percentile(times, 95), len(times),
                    {"p50": percentile(times, 50), "p95": percentile(times, 95), "unit": "ms"}, T))

    # ---- G2 FPS de procesamiento: (n-1)/(t_ultimo - t_primero) con n>=2
    ts = sorted(e["processed_epoch"] for e in ok)
    if len(ts) >= 2 and ts[-1] > ts[0]:
        fps = (len(ts) - 1) / (ts[-1] - ts[0])
        out.append(_res("G2_processing_fps", fps, len(ts), {"span_s": ts[-1] - ts[0], "unit": "frames/s"}, T))
    else:
        out.append(_res("G2_processing_fps", None, len(ts), {"reason": "menos_de_2_frames"}, T))

    # ---- G3 RAM del proceso
    rs = db.query(conn, "SELECT proc_rss_mb, proc_cpu_pct FROM resource_samples WHERE run_id=? AND ts<=?", (run_id, T))
    rss = [r["proc_rss_mb"] for r in rs if r["proc_rss_mb"] is not None]
    out.append(_res("G3_process_rss_mb", (sum(rss) / len(rss)) if rss else None, len(rss),
                    {"max": max(rss) if rss else None, "min": min(rss) if rss else None, "unit": "MB"}, T))

    # ---- G4 proporción de baja confianza
    scored = [e for e in ok if e["zone"] is not None]
    lows = sum(1 for e in scored if e["zone"] == "low")
    zc = {z: sum(1 for e in scored if e["zone"] == z) for z in ("accepted", "doubt", "low")}
    out.append(_res("G4_low_conf_share", (lows / len(scored)) if scored else None, len(scored),
                    {"low": lows, "zones": zc, "lower": scored[0]["threshold_lower"] if scored else None}, T))

    # ---- G5 cobertura de trazabilidad
    cfg_hashes = {r["config_hash"] for r in db.query(conn, "SELECT config_hash FROM config_snapshots")}
    complete = 0
    for e in ev:
        good = all(e[f] not in (None, "") for f in REQUIRED_EVENT_FIELDS)
        if good and e["status"] == "ok":
            good = all(e[f] is not None for f in ("pred_label", "confidence", "zone"))
        if good and e["config_hash"] not in cfg_hashes:
            good = False
        if good and e["capture_path"]:
            good = (data_dir / e["capture_path"]).is_file()
        complete += 1 if good else 0
    out.append(_res("G5_trace_coverage", (complete / len(ev)) if ev else None, len(ev),
                    {"complete": complete}, T))

    # ---- G6 versión esperada frente a reportada
    versions: dict[str, int] = {}
    match = 0
    exp_by_hash: dict[str, str | None] = {}
    for e in ev:
        h = e["config_hash"]
        if h not in exp_by_hash:
            row = conn.execute("SELECT config_json FROM config_snapshots WHERE config_hash=?", (h,)).fetchone()
            exp_by_hash[h] = json.loads(row["config_json"]).get("model", {}).get("expected_version") if row else None
        versions[e["model_version"]] = versions.get(e["model_version"], 0) + 1
        if exp_by_hash[h] is not None and e["model_version"] == exp_by_hash[h]:
            match += 1
    out.append(_res("G6_version_match_share", (match / len(ev)) if ev else None, len(ev),
                    {"reported_versions": versions, "expected": sorted({v for v in exp_by_hash.values() if v})}, T))

    # ---- G7 alertas activas en T
    n_active = conn.execute(
        "SELECT COUNT(*) c FROM alerts WHERE run_id=? AND fired_epoch<=? AND (resolved_epoch IS NULL OR resolved_epoch>?)",
        (run_id, T, T),
    ).fetchone()["c"]
    n_total = conn.execute("SELECT COUNT(*) c FROM alerts WHERE run_id=? AND fired_epoch<=?", (run_id, T)).fetchone()["c"]
    out.append(_res("G7_active_alerts", float(n_active), n_total, {"alerts_total": n_total}, T))

    # ================= adicionales =================
    obs = db.query(conn, "SELECT ts, kind, reason FROM stream_obs WHERE run_id=? AND ts<=?", (run_id, T))
    cap_ts = sorted(o["ts"] for o in obs if o["kind"] == "captured")
    if len(cap_ts) >= 2 and cap_ts[-1] > cap_ts[0]:
        out.append(_res("X1_capture_fps", (len(cap_ts) - 1) / (cap_ts[-1] - cap_ts[0]), len(cap_ts),
                        {"unit": "frames/s"}, T))
    else:
        out.append(_res("X1_capture_fps", None, len(cap_ts), {"reason": "menos_de_2_frames"}, T))

    dropped = [o for o in obs if o["kind"] == "dropped"]
    by_reason: dict[str, int] = {}
    for o in dropped:
        by_reason[o["reason"] or "?"] = by_reason.get(o["reason"] or "?", 0) + 1
    out.append(_res("X2_dropped_share", (len(dropped) / len(cap_ts)) if cap_ts else None, len(cap_ts),
                    {"dropped": len(dropped), "by_reason": by_reason}, T))

    cpu = [r["proc_cpu_pct"] for r in rs if r["proc_cpu_pct"] is not None]
    out.append(_res("X3_process_cpu_pct", (sum(cpu) / len(cpu)) if cpu else None, len(cpu),
                    {"max": max(cpu) if cpu else None, "unit": "% de un núcleo"}, T))

    e2e = [e["e2e_ms"] for e in ok if e["e2e_ms"] is not None]

    def _mean(col):
        v = [e[col] for e in ok if e[col] is not None]
        return (sum(v) / len(v)) if v else None

    out.append(_res("X4_e2e_ms_p95", percentile(e2e, 95), len(e2e),
                    {"p50": percentile(e2e, 50), "mean_queue_wait_ms": _mean("queue_wait_ms"),
                     "mean_preprocess_ms": _mean("preprocess_ms"), "mean_inference_ms": _mean("inference_ms"),
                     "unit": "ms"}, T))

    confs = [e["confidence"] for e in scored if e["confidence"] is not None]
    if reference and reference.get("hist_props") and len(confs) >= min_psi_samples:
        cur = histogram_props(confs, reference["hist_edges"])
        out.append(_res("X5_confidence_psi", psi(reference["hist_props"], cur), len(confs),
                        {"bins": len(cur), "reference_n": reference.get("n"), "eps": 1e-4,
                         "reference_built_at": reference.get("built_at")}, T))
    else:
        reason = "sin_referencia" if not (reference and reference.get("hist_props")) else f"menos_de_{min_psi_samples}_muestras"
        out.append(_res("X5_confidence_psi", None, len(confs), {"reason": reason}, T))

    invalid = sum(1 for e in ev if e["status"] == "invalid_input")
    out.append(_res("X6_invalid_input_rate", (invalid / len(ev)) if ev else None, len(ev),
                    {"invalid": invalid}, T))
    return out


def store_metrics(conn: sqlite3.Connection, run_id: str, results: list[dict[str, Any]]) -> None:
    for r in results:
        db.insert(conn, "metric_samples", {
            "run_id": run_id, "ts": r["ts"], "metric_id": r["metric_id"], "grp": r["grp"],
            "value": r["value"], "n": r["n"], "detail": db.jdump(r["detail"]),
        })
