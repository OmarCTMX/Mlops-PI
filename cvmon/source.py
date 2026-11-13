"""Fuentes visuales. Todas entregan Frame; los fallos se tipifican para medirlos (G2, G5)."""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests

from .config import resolve

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp"}


class SourceError(Exception):
    """La fuente no entregó datos (red, cámara caída). Dispara reconexión."""


class InvalidFrame(Exception):
    """Se recibieron bytes pero no forman una imagen válida (entrada inválida)."""

    def __init__(self, msg: str, source_ref: str | None = None):
        super().__init__(msg)
        self.source_ref = source_ref


class EndOfSource(Exception):
    """Fuente finita (video/secuencia) agotada."""


@dataclass
class Frame:
    image: np.ndarray
    captured_epoch: float
    source_ref: str | None = None
    raw_jpeg: bytes | None = None   # bytes originales de la fuente (entrada reproducible)
    meta: dict[str, Any] = field(default_factory=dict)


class FrameSource:
    finite = False

    def open(self) -> None: ...
    def read(self) -> Frame: ...
    def close(self) -> None: ...


def _decode(data: bytes, ref: str | None) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR) if arr.size else None
    if img is None or img.size == 0:
        raise InvalidFrame("No se pudo decodificar la imagen", ref)
    return img


class IPWebcamSource(FrameSource):
    """App 'IP Webcam' (Android): una petición HTTP GET /shot.jpg por frame."""

    def __init__(self, cfg: dict[str, Any]):
        self.url = cfg["url"].rstrip("/") + cfg.get("snapshot_path", "/shot.jpg")
        self.timeout = float(cfg.get("read_timeout_s", 3.0))
        self.session: requests.Session | None = None

    def open(self) -> None:
        self.session = requests.Session()
        # Comprobación de conectividad: falla pronto si la URL no responde.
        try:
            r = self.session.get(self.url, timeout=self.timeout)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise SourceError(f"No se pudo abrir {self.url}: {exc}") from exc

    def read(self) -> Frame:
        if self.session is None:
            raise SourceError("Fuente no abierta")
        t = time.time()
        try:
            r = self.session.get(self.url, timeout=self.timeout)
            r.raise_for_status()
        except requests.RequestException as exc:
            raise SourceError(f"Lectura fallida: {exc}") from exc
        img = _decode(r.content, "shot.jpg")
        return Frame(img, t, "shot.jpg", raw_jpeg=r.content)

    def close(self) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None


class WebcamSource(FrameSource):
    def __init__(self, cfg: dict[str, Any]):
        self.index = int(cfg.get("device_index", 0))
        self.cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        backend = cv2.CAP_DSHOW if sys.platform.startswith("win") else cv2.CAP_ANY
        self.cap = cv2.VideoCapture(self.index, backend)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            raise SourceError(f"No se pudo abrir la webcam {self.index}")

    def read(self) -> Frame:
        if self.cap is None:
            raise SourceError("Fuente no abierta")
        t = time.time()
        ok, img = self.cap.read()
        if not ok or img is None:
            raise SourceError("Lectura de webcam fallida")
        return Frame(img, t, f"webcam{self.index}")

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class VideoFileSource(FrameSource):
    finite = True

    def __init__(self, cfg: dict[str, Any]):
        self.path = resolve(cfg["path"])
        self.cap: cv2.VideoCapture | None = None
        self.n = 0

    def open(self) -> None:
        self.cap = cv2.VideoCapture(str(self.path))
        if not self.cap.isOpened():
            raise SourceError(f"No se pudo abrir el video {self.path}")

    def read(self) -> Frame:
        if self.cap is None:
            raise SourceError("Fuente no abierta")
        t = time.time()
        ok, img = self.cap.read()
        if not ok:
            raise EndOfSource()
        self.n += 1
        return Frame(img, t, f"{self.path.name}#{self.n}")

    def close(self) -> None:
        if self.cap is not None:
            self.cap.release()
            self.cap = None


class ImageSequenceSource(FrameSource):
    """Una imagen por lectura, en orden de nombre. Permite repetir C1/C2 con las mismas entradas."""

    finite = True

    def __init__(self, cfg: dict[str, Any]):
        self.dir = resolve(cfg["path"])
        self.files: list[Path] = []
        self.i = 0

    def open(self) -> None:
        if not self.dir.is_dir():
            raise SourceError(f"No existe el directorio de la secuencia: {self.dir}")
        self.files = sorted(p for p in self.dir.iterdir() if p.suffix.lower() in IMAGE_EXT)
        if not self.files:
            raise SourceError(f"La secuencia no contiene imágenes: {self.dir}")

    def read(self) -> Frame:
        if self.i >= len(self.files):
            raise EndOfSource()
        p = self.files[self.i]
        self.i += 1
        t = time.time()
        data = p.read_bytes()
        img = _decode(data, p.name)
        raw = data if p.suffix.lower() in {".jpg", ".jpeg"} else None
        return Frame(img, t, p.name, raw_jpeg=raw)

    def close(self) -> None: ...


def make_source(cfg: dict[str, Any]) -> FrameSource:
    kind = cfg["type"]
    if kind == "ipwebcam":
        return IPWebcamSource(cfg)
    if kind == "webcam":
        return WebcamSource(cfg)
    if kind == "video":
        return VideoFileSource(cfg)
    if kind == "sequence":
        return ImageSequenceSource(cfg)
    raise ValueError(f"Tipo de fuente desconocido: {kind}")
