"""Persistencia SQLite (modo WAL). Eventos, observaciones del stream, recursos, alertas y métricas."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS config_snapshots (
    config_hash TEXT PRIMARY KEY,
    config_json TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    scenario      TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    started_epoch REAL NOT NULL,
    ended_at      TEXT,
    ended_epoch   REAL,
    git_commit    TEXT,
    git_dirty     INTEGER,
    config_hash   TEXT NOT NULL REFERENCES config_snapshots(config_hash),
    source_id     TEXT NOT NULL,
    source_type   TEXT NOT NULL,
    model_id      TEXT NOT NULL,
    model_version TEXT NOT NULL,
    model_sha256  TEXT NOT NULL,
    model_identity_json TEXT NOT NULL,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_id        TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    seq             INTEGER NOT NULL,
    frame_id        TEXT NOT NULL,          -- frame recibido de la fuente (F-<run>-<n>)
    task            TEXT NOT NULL,          -- classification
    captured_at     TEXT NOT NULL,
    captured_epoch  REAL NOT NULL,
    processed_epoch REAL NOT NULL,
    source_id       TEXT NOT NULL,
    source_ref      TEXT,
    model_id        TEXT NOT NULL,
    model_version   TEXT NOT NULL,
    config_hash     TEXT NOT NULL REFERENCES config_snapshots(config_hash),
    threshold_lower REAL NOT NULL,
    threshold_upper REAL NOT NULL,
    status          TEXT NOT NULL,          -- ok | inference_error | invalid_input
    zone            TEXT,                   -- accepted | doubt | low | NULL (sin puntuación)
    pred_class_id   INTEGER,
    pred_label      TEXT,
    confidence      REAL,
    topk_json       TEXT,
    inference_ms    REAL,
    preprocess_ms   REAL,
    e2e_ms          REAL,                   -- captura -> resultado persistido
    queue_wait_ms   REAL,                   -- tiempo en cola antes de inferir
    capture_path    TEXT,                   -- ruta relativa a data_dir
    capture_reason  TEXT,                   -- low_confidence | doubt | normal_sample | NULL
    error_msg       TEXT,
    UNIQUE(run_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_events_run   ON events(run_id, seq);
CREATE INDEX IF NOT EXISTS idx_events_time  ON events(captured_epoch);
CREATE INDEX IF NOT EXISTS idx_events_zone  ON events(zone);

CREATE TABLE IF NOT EXISTS stream_obs (
    obs_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  TEXT NOT NULL REFERENCES runs(run_id),
    ts      REAL NOT NULL,
    kind    TEXT NOT NULL,   -- captured | dropped | read_fail | invalid_frame | reconnect_attempt | reconnect_ok
    reason  TEXT,            -- sampling | saturation | ... (para dropped)
    detail  TEXT
);
CREATE INDEX IF NOT EXISTS idx_obs_run ON stream_obs(run_id, ts);

CREATE TABLE IF NOT EXISTS resource_samples (
    sample_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    ts           REAL NOT NULL,
    proc_cpu_pct REAL,
    proc_rss_mb  REAL,
    sys_cpu_pct  REAL,
    queue_len    INTEGER,
    disk_free_gb REAL
);
CREATE INDEX IF NOT EXISTS idx_res_run ON resource_samples(run_id, ts);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id     TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES runs(run_id),
    rule_id      TEXT NOT NULL,
    rule_type    TEXT NOT NULL,
    rule_json    TEXT NOT NULL,
    config_hash  TEXT NOT NULL REFERENCES config_snapshots(config_hash),
    fired_at     TEXT NOT NULL,
    fired_epoch  REAL NOT NULL,
    severity     TEXT NOT NULL,
    reason       TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    status       TEXT NOT NULL,          -- active | resolved
    resolved_at  TEXT,
    resolved_epoch REAL,
    window_start_epoch REAL,
    window_end_epoch   REAL,
    observation_json   TEXT              -- valores observados que originaron la alerta
);
CREATE INDEX IF NOT EXISTS idx_alerts_run ON alerts(run_id, fired_epoch);

CREATE TABLE IF NOT EXISTS alert_events (
    alert_id TEXT NOT NULL REFERENCES alerts(alert_id),
    event_id TEXT NOT NULL REFERENCES events(event_id),
    PRIMARY KEY (alert_id, event_id)
);

CREATE TABLE IF NOT EXISTS rule_evaluations (
    eval_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    TEXT NOT NULL REFERENCES runs(run_id),
    rule_id   TEXT NOT NULL,
    ts        REAL NOT NULL,
    outcome   TEXT NOT NULL,   -- ok | firing | insufficient_evidence
    n_samples INTEGER,
    value     REAL,
    detail    TEXT
);
CREATE INDEX IF NOT EXISTS idx_eval_run ON rule_evaluations(run_id, rule_id, ts);

CREATE TABLE IF NOT EXISTS metric_samples (
    sample_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    TEXT NOT NULL REFERENCES runs(run_id),
    ts        REAL NOT NULL,
    metric_id TEXT NOT NULL,
    grp       TEXT NOT NULL,
    value     REAL,
    n         INTEGER,
    detail    TEXT
);
CREATE INDEX IF NOT EXISTS idx_metric_run ON metric_samples(run_id, metric_id, ts);

CREATE TABLE IF NOT EXISTS reviews (
    event_id    TEXT PRIMARY KEY REFERENCES events(event_id),
    verdict     TEXT NOT NULL,      -- correct | incorrect | unsure
    note        TEXT,
    reviewed_at TEXT NOT NULL
);
"""


def utc_iso(epoch: float | None = None) -> str:
    dt = datetime.fromtimestamp(time.time() if epoch is None else epoch, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def connect(db_path: str | Path) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def open_db(db_path: str | Path) -> sqlite3.Connection:
    conn = connect(db_path)
    init_db(conn)
    return conn


def insert(conn: sqlite3.Connection, table: str, row: dict[str, Any]) -> int:
    cols = ", ".join(row.keys())
    marks = ", ".join("?" for _ in row)
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", list(row.values()))
    return cur.lastrowid


def query(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, list(params)).fetchall()


def jdump(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
