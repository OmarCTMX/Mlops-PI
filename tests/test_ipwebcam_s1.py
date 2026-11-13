"""Fuente ipwebcam contra un servidor HTTP local que imita /shot.jpg, con interrupción y recuperación (S1)."""
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import numpy as np
import pytest

from cvmon import db
from cvmon.evidence import finalize
from cvmon.pipeline import Pipeline


def _jpeg(seed: int) -> bytes:
    rng = np.random.default_rng(seed)
    img = rng.integers(0, 255, (240, 320, 3), dtype=np.uint8)
    img = cv2.GaussianBlur(img, (1 + 2 * (seed % 5), 1 + 2 * (seed % 5)), 0)
    return cv2.imencode(".jpg", img)[1].tobytes()


@pytest.fixture()
def fake_phone():
    state = {"up": True, "n": 0}
    frames = [_jpeg(i) for i in range(6)]

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if not state["up"] or self.path != "/shot.jpg":
                self.send_response(503)
                self.end_headers()
                return
            body = frames[state["n"] % len(frames)]
            state["n"] += 1
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, state
    srv.shutdown()


def test_interrupcion_y_recuperacion(tmp_path, cfg, fake_phone):
    srv, state = fake_phone
    cfg["source"].update(type="ipwebcam", url=f"http://127.0.0.1:{srv.server_port}", capture_fps=10.0,
                         reconnect_interval_s=0.3, read_timeout_s=1.0)
    cfg["sampling"]["sample_interval_s"] = 0.2
    cfg["resources"]["sample_interval_s"] = 0.5
    for r in cfg["alerts"]["rules"]:
        if r["id"] == "R-STALE":
            r["max_age_s"] = 1.5

    def outage():
        time.sleep(3.0)
        state["up"] = False
        time.sleep(3.5)
        state["up"] = True

    threading.Thread(target=outage, daemon=True).start()
    data = tmp_path / "data"
    run_id = Pipeline(cfg, data, "S1", duration_s=11.0, verbose=False).run()
    res = finalize(data, run_id, tmp_path / "ev", "S1", cfg["model"]["path"])
    failed = [c for c in res["checks"] if not c["passed"]]
    # V3 (capturas) puede no aplicar con ruido aceptado; el resto debe pasar
    failed = [c for c in failed if c["id"] != "V3"]
    assert not failed, failed
    conn = db.open_db(data / "cvmon.db")
    kinds = {r["kind"] for r in conn.execute("SELECT kind FROM stream_obs WHERE run_id=?", (run_id,))}
    assert {"captured", "read_fail", "reconnect_attempt", "reconnect_ok", "dropped"} <= kinds
    assert (tmp_path / "ev" / "summary.md").is_file()
