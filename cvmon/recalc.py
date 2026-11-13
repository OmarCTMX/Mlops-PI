"""Recálculo INDEPENDIENTE de métricas (M5) desde las exportaciones JSONL.

No importa cvmon.metrics ni cvmon.db: reimplementa las fórmulas con numpy sobre las observaciones
primarias exportadas y compara contra el valor almacenado por el sistema en metric_samples.

Uso:  python -m cvmon recalc --export evidence/exports/C1 --data-dir data --run C1-20250101-120000
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

REQUIRED = ("event_id", "run_id", "frame_id", "task", "captured_at", "source_id", "model_id", "model_version",
            "config_hash", "status", "threshold_lower", "threshold_upper")


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _pct(vals, q):
    return float(np.percentile(np.asarray(vals, dtype=float), q)) if vals else None


def recalc_run(export_dir: str | Path, data_dir: str | Path, run_id: str) -> list[dict[str, Any]]:
    d = Path(export_dir)
    data_dir = Path(data_dir)
    events_all = [e for e in _load(d / "events.jsonl") if e["run_id"] == run_id]
    obs_all = [o for o in _load(d / "stream_obs.jsonl") if o["run_id"] == run_id]
    res_all = [r for r in _load(d / "resource_samples.jsonl") if r["run_id"] == run_id]
    alerts_all = [a for a in _load(d / "alerts.jsonl") if a["run_id"] == run_id]
    snaps = [s for s in _load(d / "config_snapshots.jsonl")]
    stored_all = [m for m in _load(d / "metric_samples.jsonl") if m["run_id"] == run_id]
    reference = None
    ref_path = d / "reference.json"
    if ref_path.is_file():
        reference = json.loads(ref_path.read_text(encoding="utf-8"))

    # Última captura de cada métrica almacenada
    last: dict[str, dict[str, Any]] = {}
    for m in sorted(stored_all, key=lambda x: x["ts"]):
        last[m["metric_id"]] = m
    if not last:
        raise SystemExit(f"No hay metric_samples para {run_id}")

    out = []
    for metric_id, stored in last.items():
        T = stored["ts"]
        ev = sorted((e for e in events_all if e["processed_epoch"] <= T), key=lambda e: e["seq"])
        ok = [e for e in ev if e["status"] == "ok"]
        scored = [e for e in ok if e["zone"] is not None]
        obs = [o for o in obs_all if o["ts"] <= T]
        res = [r for r in res_all if r["ts"] <= T]
        val: float | None
        n: int
        if metric_id == "G1_inference_ms_p95":
            v = [e["inference_ms"] for e in ok if e["inference_ms"] is not None]
            val, n = _pct(v, 95), len(v)
        elif metric_id == "G2_processing_fps":
            t = sorted(e["processed_epoch"] for e in ok)
            n = len(t)
            val = (len(t) - 1) / (t[-1] - t[0]) if len(t) >= 2 and t[-1] > t[0] else None
        elif metric_id == "G3_process_rss_mb":
            v = [r["proc_rss_mb"] for r in res if r["proc_rss_mb"] is not None]
            val, n = (float(np.mean(v)) if v else None), len(v)
        elif metric_id == "G4_low_conf_share":
            n = len(scored)
            val = (sum(1 for e in scored if e["zone"] == "low") / n) if n else None
        elif metric_id == "G5_trace_coverage":
            hashes = {s["config_hash"] for s in snaps}
            n = len(ev)
            good = 0
            for e in ev:
                g = all(e.get(f) not in (None, "") for f in REQUIRED)
                if g and e["status"] == "ok":
                    g = all(e.get(f) is not None for f in ("pred_label", "confidence", "zone"))
                g = g and e["config_hash"] in hashes
                if g and e.get("capture_path"):
                    g = (data_dir / e["capture_path"]).is_file()
                good += int(g)
            val = good / n if n else None
        elif metric_id == "G6_version_match_share":
            exp = {s["config_hash"]: json.loads(s["config_json"]).get("model", {}).get("expected_version") for s in snaps}
            n = len(ev)
            val = (sum(1 for e in ev if exp.get(e["config_hash"]) == e["model_version"]) / n) if n else None
        elif metric_id == "G7_active_alerts":
            act = [a for a in alerts_all if a["fired_epoch"] <= T and (a["resolved_epoch"] is None or a["resolved_epoch"] > T)]
            n = len([a for a in alerts_all if a["fired_epoch"] <= T])
            val = float(len(act))
        elif metric_id == "X1_capture_fps":
            t = sorted(o["ts"] for o in obs if o["kind"] == "captured")
            n = len(t)
            val = (len(t) - 1) / (t[-1] - t[0]) if len(t) >= 2 and t[-1] > t[0] else None
        elif metric_id == "X2_dropped_share":
            cap = sum(1 for o in obs if o["kind"] == "captured")
            drp = sum(1 for o in obs if o["kind"] == "dropped")
            n = cap
            val = drp / cap if cap else None
        elif metric_id == "X3_process_cpu_pct":
            v = [r["proc_cpu_pct"] for r in res if r["proc_cpu_pct"] is not None]
            val, n = (float(np.mean(v)) if v else None), len(v)
        elif metric_id == "X4_e2e_ms_p95":
            v = [e["e2e_ms"] for e in ok if e["e2e_ms"] is not None]
            val, n = _pct(v, 95), len(v)
        elif metric_id == "X5_confidence_psi":
            confs = np.array([e["confidence"] for e in scored], dtype=float)
            n = len(confs)
            if reference and reference.get("hist_props") and n >= 30:
                edges = np.array(reference["hist_edges"], dtype=float)
                idx = np.clip(np.digitize(confs, edges[1:-1], right=False), 0, len(edges) - 2)
                cur = np.bincount(idx, minlength=len(edges) - 1) / n
                exp_p = np.clip(np.array(reference["hist_props"], dtype=float), 1e-4, None)
                cur = np.clip(cur, 1e-4, None)
                val = float(np.sum((cur - exp_p) * np.log(cur / exp_p)))
            else:
                val = None
        elif metric_id == "X6_invalid_input_rate":
            n = len(ev)
            val = (sum(1 for e in ev if e["status"] == "invalid_input") / n) if n else None
        else:
            continue
        sv = stored["value"]
        if val is None or sv is None:
            match = (val is None and sv is None)
        else:
            match = math.isclose(val, sv, rel_tol=1e-6, abs_tol=1e-9)
        out.append({"metric_id": metric_id, "stored": sv, "recalculated": val, "n_stored": stored["n"],
                    "n_recalc": n, "match": bool(match and n == stored["n"]), "T": T})
    return sorted(out, key=lambda r: r["metric_id"])


def format_report(run_id: str, rows: list[dict[str, Any]]) -> str:
    lines = [f"Recálculo independiente de métricas para {run_id}", ""]
    lines.append(f"{'metric_id':<26}{'almacenado':>16}{'recalculado':>16}{'n':>8}  resultado")
    for r in rows:
        f = lambda x: "None" if x is None else f"{x:.6f}"
        lines.append(f"{r['metric_id']:<26}{f(r['stored']):>16}{f(r['recalculated']):>16}{r['n_recalc']:>8}  "
                     f"{'OK' if r['match'] else 'DIFIERE'}")
    ok = sum(1 for r in rows if r["match"])
    lines += ["", f"Coinciden {ok}/{len(rows)} métricas"]
    return "\n".join(lines)
