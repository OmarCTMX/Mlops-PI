"""Clasificador MobileNetV2 (ONNX Runtime). Inferencia real, sin generadores de confianza."""
from __future__ import annotations

import hashlib
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import onnxruntime as ort

from .config import resolve

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

PREPROCESSING = (
    "BGR->RGB; redimensionar lado corto a 256 (cv2.INTER_LINEAR); recorte central 224x224; "
    "escala /255; normalizar mean=[0.485,0.456,0.406] std=[0.229,0.224,0.225]; NCHW float32"
)


class InferenceError(RuntimeError):
    """Fallo técnico de inferencia (distinto de baja confianza)."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def softmax(logits: np.ndarray) -> np.ndarray:
    z = logits.astype(np.float64)
    z = z - z.max()
    e = np.exp(z)
    return e / e.sum()


class Classifier:
    def __init__(self, model_cfg: dict[str, Any]):
        self.cfg = model_cfg
        self.model_path = resolve(model_cfg["path"])
        self.labels_path = resolve(model_cfg["labels_path"])
        self.input_size = int(model_cfg.get("input_size", 224))
        self.topk = int(model_cfg.get("topk", 5))
        self.model_id = model_cfg["model_id"]
        self.version = model_cfg["version"]
        self.sha256 = sha256_file(self.model_path)
        expected = model_cfg.get("sha256")
        if expected and expected.upper() != self.sha256:
            raise InferenceError(
                f"El hash del modelo no coincide con la configuración ({self.sha256} != {expected})"
            )
        self.labels = self._load_labels()
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(
            str(self.model_path), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self.input_name = self.session.get_inputs()[0].name

    def _load_labels(self) -> list[str]:
        labels = []
        with open(self.labels_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                # formato synset: "n01440764 tench, Tinca tinca"
                labels.append(line.split(" ", 1)[1] if " " in line else line)
        return labels

    def preprocess(self, bgr: np.ndarray) -> np.ndarray:
        if bgr is None or bgr.ndim != 3 or bgr.shape[2] != 3 or bgr.size == 0:
            raise InferenceError("Imagen inválida para preprocesamiento")
        h, w = bgr.shape[:2]
        scale = 256.0 / min(h, w)
        nh, nw = max(int(round(h * scale)), self.input_size), max(int(round(w * scale)), self.input_size)
        img = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        top = (nh - self.input_size) // 2
        left = (nw - self.input_size) // 2
        img = img[top : top + self.input_size, left : left + self.input_size]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        rgb = (rgb - MEAN) / STD
        return np.transpose(rgb, (2, 0, 1))[np.newaxis, ...].astype(np.float32)

    def predict(self, bgr: np.ndarray) -> dict[str, Any]:
        """Ejecuta el modelo. inference_ms mide solo session.run (separado de captura y envío)."""
        t0 = time.perf_counter()
        x = self.preprocess(bgr)
        t1 = time.perf_counter()
        try:
            logits = self.session.run(None, {self.input_name: x})[0][0]
        except Exception as exc:  # noqa: BLE001 - se reporta como fallo técnico
            raise InferenceError(f"Fallo de ONNX Runtime: {exc}") from exc
        t2 = time.perf_counter()
        if logits.shape[0] != len(self.labels) or not np.all(np.isfinite(logits)):
            raise InferenceError("Salida del modelo inválida (forma o valores no finitos)")
        probs = softmax(logits)
        order = np.argsort(-probs)[: self.topk]
        top = [
            {"class_id": int(i), "label": self.labels[int(i)], "score": round(float(probs[i]), 6)}
            for i in order
        ]
        conf = float(probs[order[0]])
        if math.isnan(conf):
            raise InferenceError("Confianza NaN")
        return {
            "class_id": int(order[0]),
            "label": self.labels[int(order[0])],
            "confidence": conf,
            "topk": top,
            "preprocess_ms": (t1 - t0) * 1000.0,
            "inference_ms": (t2 - t1) * 1000.0,
        }

    def identity(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "file": str(self.model_path.relative_to(resolve("."))) if self.model_path.is_relative_to(resolve(".")) else str(self.model_path),
            "sha256": self.sha256,
            "task": self.cfg.get("task", "classification"),
            "num_classes": len(self.labels),
            "labels_file": str(self.cfg["labels_path"]),
            "input_shape": [1, 3, self.input_size, self.input_size],
            "preprocessing": PREPROCESSING,
            "confidence_definition": "softmax de la salida logits; confianza = probabilidad de la clase top-1",
            "origin": "ONNX Model Zoo (onnx/models), validated/vision/classification/mobilenet, "
                      "MobileNetV2 preentrenado en ImageNet-1k, sin reentrenar",
            "environment": environment_info(),
        }


def environment_info() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "onnxruntime": ort.__version__,
        "execution_provider": "CPUExecutionProvider",
        "opencv": cv2.__version__,
        "numpy": np.__version__,
    }
