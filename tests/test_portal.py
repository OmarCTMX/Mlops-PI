import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from cvmon import db
from cvmon.pipeline import Pipeline
from cvmon.portal.app import create_app


@pytest.fixture(scope="module")
def portal(tmp_path_factory):
    from cvmon.config import load_config

    root = tmp_path_factory.mktemp("portal")
    seq = root / "seq"
    seq.mkdir()
    rng = np.random.default_rng(3)
    for i in range(14):  # ruido borroso -> el modelo real suele dar confianzas bajas
        img = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)
        img = cv2.GaussianBlur(img, (1 + 2 * (i % 7), 1 + 2 * (i % 7)), 0)
        cv2.imwrite(str(seq / f"{i + 1:04d}.jpg"), img)
    cfg = load_config("config/config.yaml")
    cfg["source"].update(type="sequence", path=str(seq), capture_fps=50.0)
    cfg["sampling"]["sample_interval_s"] = 0
    # umbrales altos para garantizar baja confianza con ruido y observar el flujo de alertas con inferencia real
    cfg["thresholds"].update(lower=0.9, upper=0.95)
    data = root / "data"
    run_id = Pipeline(cfg, data, "T", verbose=False).run()
    app = create_app(data, "config/config.yaml")
    return TestClient(app), run_id, data


def test_paginas_principales(portal):
    client, run_id, _ = portal
    for path in ["/", "/events", "/alerts", "/metrics", "/live", "/gallery", "/runs", f"/runs/{run_id}",
                 "/health", "/api/series", "/api/live"]:
        r = client.get(path)
        assert r.status_code == 200, path
    assert 'lang="es"' in client.get("/").text


def test_eventos_filtros_y_detalle(portal):
    client, run_id, _ = portal
    r = client.get("/events", params={"run": run_id, "zone": "low"})
    assert r.status_code == 200 and "E-" in r.text
    first = db.query(db.connect(portal[2] / "cvmon.db"), "SELECT event_id FROM events LIMIT 1")[0][0]
    d = client.get(f"/events/{first}")
    assert d.status_code == 200 and "Umbrales usados" in d.text
    assert client.get("/events/NO-EXISTE").status_code == 404
    assert client.get("/events", params={"min_conf": "abc"}).status_code == 400
    assert client.get("/events", params={"min_conf": "2"}).status_code == 400
    assert client.get("/events", params={"since": "ayer"}).status_code == 400
    empty = client.get("/events", params={"label": "zzzz-no-existe"})
    assert empty.status_code == 200 and "No hay eventos" in empty.text


def test_alertas_vinculadas_a_eventos(portal):
    client, run_id, data = portal
    conn = db.connect(data / "cvmon.db")
    a = conn.execute("SELECT alert_id FROM alerts LIMIT 1").fetchone()
    assert a is not None, "con umbrales altos y ruido debe dispararse al menos una alerta real"
    page = client.get(f"/alerts/{a[0]}")
    assert page.status_code == 200 and "Acción sugerida" in page.text and "/events/E-" in page.text
    assert client.get("/alerts", params={"severity": "high"}).status_code == 200
    assert client.get("/alerts/NO-EXISTE").status_code == 404


def test_exportacion(portal):
    client, run_id, _ = portal
    csv_ = client.get("/export/events.csv", params={"run": run_id})
    assert csv_.status_code == 200 and csv_.text.startswith("event_id,")
    js = client.get("/export/events.json", params={"zone": "low"})
    assert js.status_code == 200 and isinstance(js.json(), list)
    assert client.get("/export/events.xml").status_code == 404
    assert client.get("/export/alerts.csv").status_code == 200


def test_captura_servida_y_sin_path_traversal(portal):
    client, run_id, data = portal
    conn = db.connect(data / "cvmon.db")
    cap = conn.execute("SELECT capture_path FROM events WHERE capture_path IS NOT NULL LIMIT 1").fetchone()[0]
    assert client.get("/" + cap).status_code == 200
    assert client.get("/captures/../cvmon.db").status_code in (400, 404)
    assert client.get("/captures/%2e%2e/cvmon.db").status_code in (400, 404)


def test_revision_manual(portal):
    client, run_id, data = portal
    conn = db.connect(data / "cvmon.db")
    ev = conn.execute("SELECT event_id FROM events WHERE capture_path IS NOT NULL LIMIT 1").fetchone()[0]
    r = client.post("/reviews", data={"event_id": ev, "verdict": "unsure", "note": "borroso", "back": "/gallery"},
                    follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/gallery"
    assert client.post("/reviews", data={"event_id": ev, "verdict": "xx"}).status_code == 400
    assert client.post("/reviews", data={"event_id": "no", "verdict": "correct"}).status_code == 404
    evil = client.post("/reviews", data={"event_id": ev, "verdict": "correct", "back": "//evil.com"}, follow_redirects=False)
    assert evil.headers["location"] == "/gallery"
    filtered = client.get("/gallery", params={"verdict": "unsure"})
    assert filtered.status_code == 200 and "borroso" not in "" and "unsure" in filtered.text
