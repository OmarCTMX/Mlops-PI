"""Pruebas de la LÓGICA de reglas con eventos sintéticos.

Complementan, pero no sustituyen, los escenarios C1/C2 (que usan inferencia real).
"""
from cvmon import db
from cvmon.alerts import AlertEngine
from cvmon.config import config_hash


def _engine(conn, cfg, reference=None):
    return AlertEngine(conn, cfg, "T-1", config_hash(cfg), 1000.0, reference)


def _ev(conn, i, zone, conf, status="ok"):
    row = {
        "event_id": f"E-T-1-{i:06d}", "run_id": "T-1", "seq": i, "frame_id": f"F-T-1-{i:06d}",
        "task": "classification", "captured_at": db.utc_iso(1000 + i),
        "captured_epoch": 1000.0 + i, "processed_epoch": 1000.0 + i, "source_id": "s", "model_id": "m",
        "model_version": "mobilenetv2-12", "config_hash": "x", "threshold_lower": 0.4, "threshold_upper": 0.7, "status": status,
        "zone": zone, "confidence": conf,
    }
    return row


def _insert(conn, row, cfg):
    row = dict(row)
    row["config_hash"] = config_hash(cfg)
    db.insert(conn, "events", row)


def test_evidencia_insuficiente_no_es_normalidad(conn, cfg):
    eng = _engine(conn, cfg)
    for i in range(1, 4):  # min_samples=6
        ev = _ev(conn, i, "low", 0.1)
        _insert(conn, ev, cfg)
        assert eng.on_event(ev, 1000.0 + i) == []
    outs = [r["outcome"] for r in db.query(conn, "SELECT outcome FROM rule_evaluations WHERE rule_id='R-LOWCONF'")]
    assert outs and set(outs) == {"insufficient_evidence"}


def test_baja_confianza_dispara_y_vincula_eventos(conn, cfg):
    eng = _engine(conn, cfg)
    fired = []
    for i in range(1, 9):
        ev = _ev(conn, i, "low", 0.1)
        _insert(conn, ev, cfg)
        fired += eng.on_event(ev, 1000.0 + i)
    lows = [a for a in fired if a["rule_id"] == "R-LOWCONF"]
    assert len(lows) == 1  # sin alertas repetidas mientras siga activa
    a = lows[0]
    assert a["severity"] == "high" and a["suggested_action"] and "baja confianza" in a["reason"]
    linked = db.query(conn, "SELECT event_id FROM alert_events WHERE alert_id=?", (a["alert_id"],))
    assert len(linked) >= 6
    assert a["config_hash"] == config_hash(cfg)


def test_alerta_se_resuelve_con_recuperacion(conn, cfg):
    eng = _engine(conn, cfg)
    for i in range(1, 8):
        ev = _ev(conn, i, "low", 0.1)
        _insert(conn, ev, cfg)
        eng.on_event(ev, 1000.0 + i)
    for i in range(8, 24):
        ev = _ev(conn, i, "accepted", 0.9)
        _insert(conn, ev, cfg)
        eng.on_event(ev, 1000.0 + i)
    st = conn.execute("SELECT status, resolved_epoch FROM alerts WHERE rule_id='R-LOWCONF'").fetchone()
    assert st["status"] == "resolved" and st["resolved_epoch"] is not None


def test_cambio_sostenido_requiere_persistencia_y_referencia(conn, cfg):
    ref = {"n": 100, "mean": 0.85}
    eng = _engine(conn, cfg, ref)
    fired = []
    for i in range(1, 40):
        ev = _ev(conn, i, "doubt", 0.55)  # media 0.55 << 0.85 - 0.15
        _insert(conn, ev, cfg)
        fired += eng.on_event(ev, 1000.0 + i)
    shifts = [a for a in fired if a["rule_id"] == "R-SHIFT"]
    assert len(shifts) == 1
    # no se dispara en la primera evaluación con ventana suficiente (persistencia = 5)
    first_eval = db.query(conn, "SELECT outcome FROM rule_evaluations WHERE rule_id='R-SHIFT' ORDER BY eval_id")
    assert "pending" in [r["outcome"] for r in first_eval]


def test_cambio_sostenido_sin_referencia_es_insuficiente(conn, cfg):
    eng = _engine(conn, cfg, None)
    for i in range(1, 30):
        ev = _ev(conn, i, "low", 0.1)
        _insert(conn, ev, cfg)
        eng.on_event(ev, 1000.0 + i)
    outs = {r["outcome"] for r in db.query(conn, "SELECT outcome FROM rule_evaluations WHERE rule_id='R-SHIFT'")}
    assert outs == {"insufficient_evidence"}


def test_stream_stale_dispara_y_recupera(conn, cfg):
    eng = _engine(conn, cfg)
    assert eng.on_tick(1005.0, None) == []            # < max_age: evidencia insuficiente
    a = eng.on_tick(1020.0, None)                     # sin frames desde el inicio
    assert len(a) == 1 and a[0]["severity"] == "critical"
    assert eng.on_tick(1021.0, 1000.0) == []          # sigue activa, sin duplicar
    eng.on_tick(1022.0, 1021.5)                       # frame reciente -> se resuelve
    assert conn.execute("SELECT status FROM alerts").fetchone()["status"] == "resolved"


def test_version_distinta_de_la_esperada(conn, cfg):
    eng = _engine(conn, cfg)
    fired = []
    for i in range(1, 8):
        ev = _ev(conn, i, "accepted", 0.9)
        ev["model_version"] = "otra-version"
        _insert(conn, ev, cfg)
        fired += eng.on_event(ev, 1000.0 + i)
    a = [x for x in fired if x["rule_id"] == "R-VERSION"]
    assert len(a) == 1 and "otra-version" in a[0]["reason"]
    # al volver a la versión esperada se resuelve
    for i in range(8, 14):
        ev = _ev(conn, i, "accepted", 0.9)
        _insert(conn, ev, cfg)
        eng.on_event(ev, 1000.0 + i)
    assert conn.execute("SELECT status FROM alerts WHERE rule_id='R-VERSION'").fetchone()["status"] == "resolved"


def test_tasa_de_errores(conn, cfg):
    eng = _engine(conn, cfg)
    fired = []
    for i in range(1, 8):
        ev = _ev(conn, i, None, None, status="inference_error")
        _insert(conn, ev, cfg)
        fired += eng.on_event(ev, 1000.0 + i)
    assert [a["rule_id"] for a in fired] == ["R-INFERR"]
