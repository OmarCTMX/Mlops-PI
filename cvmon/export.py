"""Exportación de las tablas a JSONL/CSV (observaciones primarias recalculables)."""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

TABLES = [
    "config_snapshots", "runs", "events", "stream_obs", "resource_samples",
    "alerts", "alert_events", "rule_evaluations", "metric_samples", "reviews",
]


def export_jsonl(conn: sqlite3.Connection, out_dir: str | Path, run_ids: list[str] | None = None) -> dict[str, int]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for t in TABLES:
        sql = f"SELECT * FROM {t}"
        params: list = []
        if run_ids and t in {"runs", "events", "stream_obs", "resource_samples", "alerts",
                             "rule_evaluations", "metric_samples"}:
            sql += f" WHERE run_id IN ({','.join('?' for _ in run_ids)})"
            params = list(run_ids)
        rows = conn.execute(sql, params).fetchall()
        if run_ids and t == "alert_events":
            ids = {r["alert_id"] for r in conn.execute(
                f"SELECT alert_id FROM alerts WHERE run_id IN ({','.join('?' for _ in run_ids)})", run_ids)}
            rows = [r for r in rows if r["alert_id"] in ids]
        if run_ids and t == "reviews":
            ev = {r["event_id"] for r in conn.execute(
                f"SELECT event_id FROM events WHERE run_id IN ({','.join('?' for _ in run_ids)})", run_ids)}
            rows = [r for r in rows if r["event_id"] in ev]
        with open(out / f"{t}.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for r in rows:
                fh.write(json.dumps(dict(r), ensure_ascii=False, sort_keys=True) + "\n")
        counts[t] = len(rows)
    return counts


def rows_to_csv(rows: list[sqlite3.Row], columns: list[str] | None = None) -> str:
    import io

    buf = io.StringIO()
    if not rows:
        return ""
    cols = columns or list(rows[0].keys())
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow([r[c] for c in cols])
    return buf.getvalue()
