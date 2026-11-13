"""Las entradas guardadas de un run en vivo reproducen exactamente los mismos scores (M5, R7.2)."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import cv2
import numpy as np

from cvmon.evidence import replay_check
from cvmon.pipeline import Pipeline


def test_replay_identico(tmp_path, cfg):
    frames = []
    for i in range(4):
        rng = np.random.default_rng(100 + i)
        img = cv2.GaussianBlur(rng.integers(0, 255, (240, 320, 3), dtype=np.uint8), (5, 5), 0)
        frames.append(cv2.imencode(".jpg", img)[1].tobytes())
    n = {"i": 0}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = frames[n["i"] % len(frames)]
            n["i"] += 1
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        cfg["source"].update(type="ipwebcam", url=f"http://127.0.0.1:{srv.server_port}", capture_fps=20.0)
        cfg["sampling"]["sample_interval_s"] = 0.1
        data = tmp_path / "data"
        inputs = tmp_path / "inputs"
        live = Pipeline(cfg, data, "LIVE", max_events=8, record_inputs=inputs, verbose=False).run()
    finally:
        srv.shutdown()
    assert len(list(inputs.glob("*.jpg"))) == 8

    cfg2 = dict(cfg)
    cfg2["source"] = dict(cfg["source"], type="sequence", path=str(inputs), capture_fps=50.0)
    cfg2["sampling"] = dict(cfg["sampling"], sample_interval_s=0)
    replay = Pipeline(cfg2, data, "REPLAY", verbose=False).run()
    res = replay_check(data, live, replay)
    assert res["identical"], res
    assert res["compared"] == 8 and res["max_abs_diff"] == 0.0
