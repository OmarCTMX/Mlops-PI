"""Pipeline: fuente -> muestreo -> modelo real -> política -> evento + captura -> alertas -> métricas."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import psutil

from . import db
from .alerts import AlertEngine
from .config import ROOT, config_hash, resolve
from .metrics import compute_all, store_metrics
from .model import Classifier, InferenceError
from .policy import (
    STATUS_INFERENCE_ERROR, STATUS_INVALID_INPUT, STATUS_OK,
    ZONE_ACCEPTED, ZONE_DOUBT, ZONE_LOW, classify_zone,
)
from .source import EndOfSource, Frame, InvalidFrame, SourceError, make_source

ZONE_COLORS = {ZONE_ACCEPTED: (80, 175, 76), ZONE_DOUBT: (0, 165, 255), ZONE_LOW: (60, 60, 220)}
_INVALID = object()


def git_info() -> tuple[str | None, int | None]:
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=10)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", ".", ":!data", ":!evidence", ":!data-dev"],
                               cwd=ROOT, capture_output=True, text=True, timeout=10)
        if commit.returncode != 0:
            return None, None
        return commit.stdout.strip(), 1 if dirty.stdout.strip() else 0
    except (OSError, subprocess.SubprocessError):
        return None, None


def load_reference(cfg: dict[str, Any]) -> dict[str, Any] | None:
    p = resolve(cfg.get("reference", {}).get("path", "config/reference.json"))
    if p.is_file():
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    return None


class Pipeline:
    def __init__(
        self,
        cfg: dict[str, Any],
        data_dir: str | Path,
        scenario: str,
        duration_s: float | None = None,
        max_events: int | None = None,
        record_inputs: str | Path | None = None,
        notes: str | None = None,
        verbose: bool = True,
        classifier: Classifier | None = None,
    ):
        self.cfg = cfg
        self.data_dir = Path(data_dir)
        self.scenario = scenario
        self.duration_s = duration_s
        self.max_events = max_events
        self.record_inputs = Path(record_inputs) if record_inputs else None
        self.notes = notes
        self.verbose = verbose
        self.stop_event = threading.Event()
        self.reader_done = threading.Event()
        self.last_frame_epoch: float | None = None
        self.q: queue.Queue = queue.Queue(maxsize=int(cfg["sampling"]["queue_size"]))
        self.clf = classifier or Classifier(cfg["model"])
        self.cfg_hash = config_hash(cfg)
        self.reference = load_reference(cfg)
        self.lower = float(cfg["thresholds"]["lower"])
        self.upper = float(cfg["thresholds"]["upper"])
        self.seq = 0
        self.n_accepted = 0
        self.n_inputs = 0
        self.run_id: str = ""

    # ------------------------------------------------------------- lectura
    def _reader(self) -> None:
        conn = db.connect(self.data_dir / "cvmon.db")
        scfg = self.cfg["source"]
        samp = float(self.cfg["sampling"]["sample_interval_s"])
        period = 1.0 / float(scfg.get("capture_fps", 5.0))
        reconnect_s = float(scfg.get("reconnect_interval_s", 2.0))
        src = make_source(scfg)
        self._finite_source = bool(src.finite)
        connected = False
        last_sample: float | None = None

        def obs(kind, reason=None, detail=None):
            db.insert(conn, "stream_obs", {"run_id": self.run_id, "ts": time.time(), "kind": kind,
                                           "reason": reason, "detail": detail})

        try:
            while not self.stop_event.is_set():
                t0 = time.time()
                if not connected:
                    try:
                        src.open()
                        connected = True
                        if self._was_connected_before:
                            obs("reconnect_ok")
                    except SourceError as exc:
                        # primer intento fallido = fallo de lectura; los siguientes = intentos de reconexión
                        obs("reconnect_attempt" if self._was_connected_before else "read_fail",
                            detail=str(exc)[:200])
                        self._sleep(reconnect_s)
                        continue
                    self._was_connected_before = True
                try:
                    fr = src.read()
                except EndOfSource:
                    break
                except SourceError as exc:
                    obs("read_fail", detail=str(exc)[:200])
                    src.close()
                    connected = False
                    self._sleep(reconnect_s)
                    continue
                except InvalidFrame as exc:
                    self.frame_no += 1
                    obs("invalid_frame", detail=f"{self._frame_id()} {exc.source_ref}: {exc}"[:200])
                    self._offer(_INVALID, str(exc), exc.source_ref, conn, self._frame_id())
                    self._sleep(max(0.0, period - (time.time() - t0)))
                    continue
                self.last_frame_epoch = fr.captured_epoch
                self.frame_no += 1
                fid = self._frame_id()
                obs("captured", detail=f"{fid} {fr.source_ref}")
                take = last_sample is None or samp == 0 or (fr.captured_epoch - last_sample) >= samp
                if take:
                    last_sample = fr.captured_epoch
                    self._offer(fr, None, None, conn, fid)
                else:
                    obs("dropped", "sampling", fid)
                self._sleep(max(0.0, period - (time.time() - t0)))
        finally:
            src.close()
            conn.close()
            self.reader_done.set()

    _was_connected_before = False

    _finite_source = False
    frame_no = 0

    def _frame_id(self) -> str:
        """Identificador del frame recibido de la fuente (contador por run, incluye frames no inferidos)."""
        return f"F-{self.run_id}-{self.frame_no:06d}"

    def _offer(self, item, err, ref, conn, frame_id: str) -> bool:
        try:
            if self._finite_source:
                # Fuente finita (video/secuencia): contrapresión, no se pierden frames por saturación.
                while not self.stop_event.is_set():
                    try:
                        self.q.put((item, time.time(), err, ref, frame_id), timeout=0.2)
                        return True
                    except queue.Full:
                        continue
                return False
            self.q.put_nowait((item, time.time(), err, ref, frame_id))
            return True
        except queue.Full:
            db.insert(conn, "stream_obs", {"run_id": self.run_id, "ts": time.time(), "kind": "dropped",
                                           "reason": "saturation", "detail": frame_id})
            return False

    def _sleep(self, s: float) -> None:
        if s > 0:
            self.stop_event.wait(s)

    # ------------------------------------------------------------ ejecución
    def run(self) -> str:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        conn = db.open_db(self.data_dir / "cvmon.db")
        started = time.time()
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(started))
        self.run_id = f"{self.scenario}-{stamp}"
        commit, dirty = git_info()
        ident = self.clf.identity()
        conn.execute("INSERT OR IGNORE INTO config_snapshots(config_hash, config_json, created_at) VALUES (?,?,?)",
                     (self.cfg_hash, db.jdump(self.cfg), db.utc_iso(started)))
        db.insert(conn, "runs", {
            "run_id": self.run_id, "scenario": self.scenario, "started_at": db.utc_iso(started),
            "started_epoch": started, "git_commit": commit, "git_dirty": dirty, "config_hash": self.cfg_hash,
            "source_id": self.cfg["source"]["id"], "source_type": self.cfg["source"]["type"],
            "model_id": ident["model_id"], "model_version": ident["version"], "model_sha256": ident["sha256"],
            "model_identity_json": db.jdump(ident), "notes": self.notes,
        })
        engine = AlertEngine(conn, self.cfg, self.run_id, self.cfg_hash, started, self.reference)
        if self.record_inputs:
            self.record_inputs.mkdir(parents=True, exist_ok=True)
        proc = psutil.Process(os.getpid())
        proc.cpu_percent(None)
        res_every = float(self.cfg.get("resources", {}).get("sample_interval_s", 2.0))
        met_every = float(self.cfg.get("metrics", {}).get("snapshot_interval_s", 10))
        next_res = started
        next_met = started + met_every
        next_tick = started

        if self.verbose:
            print(f"[run] {self.run_id} commit={commit} cfg={self.cfg_hash} modelo={ident['model_id']} "
                  f"fuente={self.cfg['source']['id']} umbrales=({self.lower},{self.upper})", flush=True)
        th = threading.Thread(target=self._reader, name="reader", daemon=True)
        th.start()
        try:
            while True:
                now = time.time()
                if self.duration_s and now - started >= self.duration_s:
                    break
                if self.max_events and self.seq >= self.max_events:
                    break
                if self.reader_done.is_set() and self.q.empty():
                    break
                try:
                    item, enq, err, ref, fid = self.q.get(timeout=0.2)
                except queue.Empty:
                    item = None
                if item is not None:
                    self._handle(conn, engine, item, enq, err, ref, fid)
                now = time.time()
                if now >= next_tick:
                    next_tick = now + 1.0
                    for a in engine.on_tick(now, self.last_frame_epoch):
                        self._announce_alert(a)
                if now >= next_res:
                    next_res = now + res_every
                    self._sample_resources(conn, proc)
                if now >= next_met:
                    next_met = now + met_every
                    store_metrics(conn, self.run_id, compute_all(conn, self.run_id, self.data_dir, self.reference, T=now))
        except KeyboardInterrupt:
            print("[run] interrumpido por el usuario", flush=True)
        finally:
            self.stop_event.set()
            th.join(timeout=10)
            ended = time.time()
            self._sample_resources(conn, proc)
            conn.execute("UPDATE runs SET ended_at=?, ended_epoch=? WHERE run_id=?",
                         (db.utc_iso(ended), ended, self.run_id))
            store_metrics(conn, self.run_id, compute_all(conn, self.run_id, self.data_dir, self.reference, T=ended))
            if self.verbose:
                print(f"[run] terminado: {self.seq} eventos, run_id={self.run_id}", flush=True)
            conn.close()
        return self.run_id

    # ---------------------------------------------------------------- eventos
    def _handle(self, conn, engine: AlertEngine, item, enq: float, err: str | None, ref: str | None,
                frame_id: str) -> None:
        self.seq += 1
        event_id = f"E-{self.run_id}-{self.seq:06d}"
        deq = time.time()
        row: dict[str, Any] = {
            "event_id": event_id, "run_id": self.run_id, "seq": self.seq, "frame_id": frame_id,
            "task": self.cfg["model"].get("task", "classification"),
            "source_id": self.cfg["source"]["id"], "model_id": self.clf.model_id,
            "model_version": self.clf.version, "config_hash": self.cfg_hash,
            "threshold_lower": self.lower, "threshold_upper": self.upper,
            "queue_wait_ms": (deq - enq) * 1000.0,
        }
        frame: Frame | None = None
        if item is _INVALID:
            row.update(captured_epoch=enq, captured_at=db.utc_iso(enq), source_ref=ref, status=STATUS_INVALID_INPUT,
                       error_msg=err)
        else:
            frame = item
            row.update(captured_epoch=frame.captured_epoch, captured_at=db.utc_iso(frame.captured_epoch),
                       source_ref=frame.source_ref)
            if self.record_inputs is not None:
                self._record_input(frame)
            try:
                pred = self.clf.predict(frame.image)
                row.update(status=STATUS_OK, pred_class_id=pred["class_id"], pred_label=pred["label"],
                           confidence=pred["confidence"], topk_json=db.jdump(pred["topk"]),
                           inference_ms=pred["inference_ms"], preprocess_ms=pred["preprocess_ms"],
                           zone=classify_zone(pred["confidence"], self.lower, self.upper))
            except InferenceError as exc:
                row.update(status=STATUS_INFERENCE_ERROR, error_msg=str(exc)[:300])
        done = time.time()
        row["processed_epoch"] = done
        row["e2e_ms"] = (done - row["captured_epoch"]) * 1000.0

        if frame is not None:
            reason = self._capture_reason(row)
            if reason:
                rel = Path("captures") / self.run_id / f"{event_id}.jpg"
                self._save_capture(frame, self.data_dir / rel)
                row["capture_path"] = rel.as_posix()
                row["capture_reason"] = reason
        db.insert(conn, "events", row)
        if frame is not None and row["status"] == STATUS_OK:
            self._write_live(frame, row)
        if self.verbose:
            conf = f"{row['confidence']:.3f}" if row.get("confidence") is not None else "  -  "
            print(f"[evt] {event_id} {row['status']:<15} {str(row.get('zone')):<8} {conf} "
                  f"{(row.get('pred_label') or '')[:28]:<28} inf={row.get('inference_ms') or 0:6.1f}ms"
                  f"{' [captura:' + row['capture_reason'] + ']' if row.get('capture_reason') else ''}", flush=True)
        for a in engine.on_event(row, time.time()):
            self._announce_alert(a)

    def _announce_alert(self, a: dict[str, Any]) -> None:
        if self.verbose:
            print(f"[ALERTA] {a['alert_id']} {a['rule_id']} sev={a['severity']}: {a['reason']}", flush=True)

    def _capture_reason(self, row: dict[str, Any]) -> str | None:
        cap = self.cfg["capture"]
        if row["status"] != STATUS_OK:
            return "inference_error" if cap.get("save_on_error") else None
        zone = row["zone"]
        if zone == ZONE_LOW and ZONE_LOW in cap["save_zones"]:
            return "low_confidence"
        if zone == ZONE_DOUBT and ZONE_DOUBT in cap["save_zones"]:
            return "doubt"
        if zone == ZONE_ACCEPTED:
            self.n_accepted += 1
            n = int(cap.get("normal_sample_every_n", 0))
            if ZONE_ACCEPTED in cap["save_zones"]:
                return "accepted"
            if n > 0 and (self.n_accepted - 1) % n == 0:
                return "normal_sample"
        return None

    @staticmethod
    def _encode(frame: Frame, quality: int = 90) -> bytes:
        if frame.raw_jpeg:
            return frame.raw_jpeg
        ok, buf = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        if not ok:
            raise RuntimeError("No se pudo codificar la captura")
        return buf.tobytes()

    def _save_capture(self, frame: Frame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self._encode(frame, int(self.cfg["capture"].get("jpeg_quality", 90))))

    def _record_input(self, frame: Frame) -> None:
        self.n_inputs += 1
        (self.record_inputs / f"{self.n_inputs:04d}.jpg").write_bytes(self._encode(frame))

    # ------------------------------------------------------------ recursos / live
    def _sample_resources(self, conn, proc: psutil.Process) -> None:
        try:
            disk = psutil.disk_usage(str(self.data_dir.resolve())).free / 1e9
            db.insert(conn, "resource_samples", {
                "run_id": self.run_id, "ts": time.time(), "proc_cpu_pct": proc.cpu_percent(None),
                "proc_rss_mb": proc.memory_info().rss / 1e6, "sys_cpu_pct": psutil.cpu_percent(None),
                "queue_len": self.q.qsize(), "disk_free_gb": disk,
            })
        except (psutil.Error, OSError):
            pass

    def _write_live(self, frame: Frame, row: dict[str, Any]) -> None:
        try:
            img = frame.image
            h, w = img.shape[:2]
            if w > 640:
                img = cv2.resize(img, (640, int(h * 640 / w)))
            img = img.copy()
            color = ZONE_COLORS.get(row["zone"], (200, 200, 200))
            text = f"{row['pred_label'][:32]}  {row['confidence']:.2f}  [{row['zone']}]"
            cv2.rectangle(img, (0, 0), (img.shape[1], 30), (0, 0, 0), -1)
            cv2.putText(img, text, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2, cv2.LINE_AA)
            live = self.data_dir / "live"
            live.mkdir(exist_ok=True)
            ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                tmp = live / "latest.tmp"
                tmp.write_bytes(buf.tobytes())
                os.replace(tmp, live / "latest.jpg")
            meta = {"event_id": row["event_id"], "run_id": row["run_id"], "label": row["pred_label"],
                    "confidence": row["confidence"], "zone": row["zone"], "captured_epoch": row["captured_epoch"],
                    "inference_ms": row["inference_ms"]}
            (live / "latest.json").write_text(json.dumps(meta), encoding="utf-8")
        except OSError:
            pass  # el portal puede estar leyendo el archivo; se reintenta en el siguiente evento
