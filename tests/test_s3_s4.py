"""S3 (entrada inválida) y S4 (cambio de versión con dos artefactos reales) de punta a punta."""
import cv2
import numpy as np
import pytest

from cvmon.evidence import finalize
from cvmon.pipeline import Pipeline

V7_SHA = "C1C513582D56AFCEFF8516C73804E484C81C6A830712AB6D682253F4A3CD042F"


@pytest.fixture()
def seq(tmp_path):
    d = tmp_path / "seq"
    d.mkdir()
    rng = np.random.default_rng(11)
    for i in range(12):
        img = cv2.GaussianBlur(rng.integers(0, 255, (240, 320, 3), dtype=np.uint8), (1 + 2 * (i % 4),) * 2, 0)
        cv2.imwrite(str(d / f"{i + 1:04d}.jpg"), img)
    return d


def _fast(cfg, seq):
    cfg["source"].update(type="sequence", path=str(seq), capture_fps=50.0)
    cfg["sampling"]["sample_interval_s"] = 0
    cfg["resources"]["sample_interval_s"] = 0.1
    return cfg


def test_s3_entradas_invalidas(tmp_path, cfg, seq):
    for i in (2, 5, 9):  # trunca 3 imágenes: falla de la entrada, no del modelo
        p = seq / f"{i:04d}.jpg"
        p.write_bytes(p.read_bytes()[:200])
    _fast(cfg, seq)
    run = Pipeline(cfg, tmp_path / "d", "S3", verbose=False).run()
    res = finalize(tmp_path / "d", run, tmp_path / "ev", "S3", cfg["model"]["path"])
    bad = [c for c in res["checks"] if not c["passed"] and c["id"].startswith(("S3", "V1", "V2", "V5"))]
    assert not bad, bad
    x6 = [r for r in res["recalc"] if r["metric_id"] == "X6_invalid_input_rate"][0]
    assert x6["match"] and abs(x6["recalculated"] - 3 / 12) < 1e-9


def test_s4_cambio_de_version(tmp_path, cfg, seq):
    _fast(cfg, seq)
    data = tmp_path / "d"
    Pipeline(cfg, data, "C1", verbose=False).run()          # artefacto base
    cfg["model"].update(path="models/mobilenetv2-7.onnx", sha256=V7_SHA, version="mobilenetv2-7")
    run = Pipeline(cfg, data, "S4", verbose=False).run()    # expected_version sigue siendo mobilenetv2-12
    res = finalize(data, run, tmp_path / "ev", "S4", cfg["model"]["path"])
    bad = [c for c in res["checks"] if not c["passed"] and c["id"].startswith(("S4", "V1", "V2", "V4", "V5"))]
    assert not bad, bad
