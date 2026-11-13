"""Cadena real: imágenes -> modelo ONNX real -> eventos -> métricas -> recálculo independiente."""
import json

import cv2
import numpy as np
import pytest

from cvmon import db
from cvmon.export import export_jsonl
from cvmon.metrics import percentile
from cvmon.pipeline import Pipeline
from cvmon.recalc import recalc_run


@pytest.fixture(scope="module")
def seq_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("seq")
    rng = np.random.default_rng(7)
    for i in range(10):
        img = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)
        img = cv2.GaussianBlur(img, (1 + 2 * i, 1 + 2 * i), 0)
        cv2.imwrite(str(d / f"{i + 1:04d}.jpg"), img)
    (d / "0011_corrupta.jpg").write_bytes(b"\xff\xd8\xff not a jpeg")
    return d


def test_percentile_lineal():
    assert percentile([1, 2, 3, 4], 50) == 2.5
    assert percentile([], 95) is None
    assert percentile([5], 95) == 5.0


def test_pipeline_y_recalculo(tmp_path, cfg, seq_dir):
    cfg["source"].update(type="sequence", path=str(seq_dir), capture_fps=50.0)
    cfg["sampling"]["sample_interval_s"] = 0
    cfg["resources"]["sample_interval_s"] = 0.1
    data = tmp_path / "data"
    run_id = Pipeline(cfg, data, "T", verbose=False).run()
    conn = db.open_db(data / "cvmon.db")
    ev = db.query(conn, "SELECT * FROM events WHERE run_id=? ORDER BY seq", (run_id,))
    assert len(ev) == 11
    assert sum(1 for e in ev if e["status"] == "invalid_input") == 1   # la imagen corrupta
    ok = [e for e in ev if e["status"] == "ok"]
    assert all(e["confidence"] is not None and 0 <= e["confidence"] <= 1 for e in ok)
    assert all(e["zone"] in ("accepted", "doubt", "low") for e in ok)
    assert all(e["zone"] is None and e["confidence"] is None for e in ev if e["status"] != "ok")
    for e in ev:  # capturas referenciadas existen
        if e["capture_path"]:
            assert (data / e["capture_path"]).is_file()
    export_jsonl(conn, tmp_path / "exp")
    rows = recalc_run(tmp_path / "exp", data, run_id)
    assert rows and all(r["match"] for r in rows), [r for r in rows if not r["match"]]
    ids = {r["metric_id"] for r in rows}
    assert {"G1_inference_ms_p95", "G2_processing_fps", "G3_process_rss_mb", "G4_low_conf_share",
            "G5_trace_coverage", "G6_version_match_share", "G7_active_alerts"} <= ids


def test_cero_observaciones_es_none_no_cero(tmp_path, cfg):
    from cvmon.metrics import compute_all

    conn = db.open_db(tmp_path / "e.db")
    from cvmon.config import config_hash
    conn.execute("INSERT INTO config_snapshots VALUES (?,?,?)", (config_hash(cfg), "{}", db.utc_iso()))
    conn.execute("INSERT INTO runs(run_id,scenario,started_at,started_epoch,config_hash,source_id,source_type,model_id,"
                 "model_version,model_sha256,model_identity_json) VALUES ('E','E',?,1.0,?,'s','sequence','m','v','x','{}')",
                 (db.utc_iso(1.0), config_hash(cfg)))
    res = {r["metric_id"]: r for r in compute_all(conn, "E", tmp_path)}
    assert res["G1_inference_ms_p95"]["value"] is None
    assert res["G4_low_conf_share"]["value"] is None
    assert res["G4_low_conf_share"]["detail"]["reason"] == "sin_observaciones"
    assert res["G7_active_alerts"]["value"] == 0.0
