"""Motor de reglas de alerta (R5).

Cada regla produce, en cada evaluación, uno de estos resultados (se registran en rule_evaluations):
    ok                     condición no cumplida con evidencia suficiente
    pending                condición cumplida pero aún sin la persistencia exigida
    firing                 condición cumplida (alerta activa)
    insufficient_evidence  menos observaciones que el mínimo: NO se interpreta como normalidad
Las alertas se generan SOLO a partir de eventos/observaciones reales del pipeline y se vinculan a
la regla (rule_json), la configuración (config_hash) y los eventos de la ventana (alert_events).
"""
from __future__ import annotations

import sqlite3
from collections import deque
from typing import Any

from . import db
from .policy import STATUS_INFERENCE_ERROR, STATUS_OK, ZONE_LOW

OK = "ok"
PENDING = "pending"
FIRING = "firing"
INSUFFICIENT = "insufficient_evidence"


class AlertEngine:
    def __init__(
        self,
        conn: sqlite3.Connection,
        cfg: dict[str, Any],
        run_id: str,
        config_hash: str,
        run_start_epoch: float,
        reference: dict[str, Any] | None = None,
    ):
        self.conn = conn
        self.cfg = cfg
        self.run_id = run_id
        self.config_hash = config_hash
        self.run_start = run_start_epoch
        self.reference = reference
        self.rules = cfg["alerts"]["rules"]
        self.log_every = float(cfg["alerts"].get("evaluation_log_every_s", 10))
        self.n_alerts = 0
        self.state: dict[str, dict[str, Any]] = {
            r["id"]: {"active": None, "last_outcome": None, "last_log": 0.0, "consec": 0} for r in self.rules
        }
        # ventanas de eventos recientes: (event_id, epoch, zone, confidence, status)
        maxlen = max([int(r.get("window_events", 1)) for r in self.rules] + [1])
        self.scored: deque = deque(maxlen=maxlen)     # eventos con puntuación (status ok)
        self.attempts: deque = deque(maxlen=maxlen)   # intentos de inferencia (ok + error)
        self.versions: deque = deque(maxlen=maxlen)   # (event_id, epoch, version_reportada)
        self.expected_version = cfg.get("model", {}).get("expected_version")
        self.last_event_id: str | None = None

    # ------------------------------------------------------------------ API
    def on_event(self, ev: dict[str, Any], now: float) -> list[dict[str, Any]]:
        self.last_event_id = ev["event_id"]
        rec = (ev["event_id"], ev["captured_epoch"], ev.get("zone"), ev.get("confidence"), ev["status"])
        if ev["status"] == STATUS_OK:
            self.scored.append(rec)
        if ev["status"] in (STATUS_OK, STATUS_INFERENCE_ERROR):
            self.attempts.append(rec)
        self.versions.append((ev["event_id"], ev["captured_epoch"], ev.get("model_version")))
        fired = []
        for rule in self.rules:
            t = rule["type"]
            if t == "low_confidence_share":
                a = self._eval_low_share(rule, now)
            elif t == "confidence_shift":
                a = self._eval_shift(rule, now)
            elif t == "inference_error_rate":
                a = self._eval_error_rate(rule, now)
            elif t == "version_mismatch":
                a = self._eval_version(rule, now)
            else:
                continue
            if a:
                fired.append(a)
        return fired

    def on_tick(self, now: float, last_frame_epoch: float | None) -> list[dict[str, Any]]:
        fired = []
        for rule in self.rules:
            if rule["type"] == "stream_stale":
                a = self._eval_stale(rule, now, last_frame_epoch)
                if a:
                    fired.append(a)
        return fired

    def active_alerts(self) -> list[str]:
        return [s["active"] for s in self.state.values() if s["active"]]

    # ------------------------------------------------------------- reglas
    def _eval_low_share(self, rule, now):
        n_req = int(rule["window_events"])
        win = list(self.scored)[-n_req:]
        n = len(win)
        if n < int(rule["min_samples"]):
            self._log(rule, now, INSUFFICIENT, n, None, f"{n} < min_samples={rule['min_samples']}")
            return None
        lows = sum(1 for w in win if w[2] == ZONE_LOW)
        share = lows / n
        st = self.state[rule["id"]]
        cond = share >= float(rule["fire_share"])
        if st["active"]:
            if share < float(rule["clear_share"]):
                self._resolve(rule, now, f"proporción de baja confianza {share:.2f} < {rule['clear_share']}")
                self._log(rule, now, OK, n, share, "resuelta")
            else:
                self._log(rule, now, FIRING, n, share, "activa")
            return None
        if cond:
            reason = (
                f"{lows} de las últimas {n} inferencias con puntuación cayeron en baja confianza "
                f"(proporción {share:.2f} >= {rule['fire_share']}; umbral inferior "
                f"{self.cfg['thresholds']['lower']})"
            )
            self._log(rule, now, FIRING, n, share, "disparada")
            return self._fire(rule, now, reason, win, {"share": share, "lows": lows, "n": n})
        self._log(rule, now, OK, n, share, "")
        return None

    def _eval_shift(self, rule, now):
        st = self.state[rule["id"]]
        ref = self.reference
        if not ref or ref.get("n", 0) < int(self.cfg.get("reference", {}).get("min_observations", 1)):
            self._log(rule, now, INSUFFICIENT, 0, None, "referencia ausente o con pocas observaciones")
            return None
        n_req = int(rule["window_events"])
        win = list(self.scored)[-n_req:]
        n = len(win)
        if n < int(rule["min_samples"]):
            self._log(rule, now, INSUFFICIENT, n, None, f"{n} < min_samples={rule['min_samples']}")
            return None
        mean = sum(w[3] for w in win) / n
        drop = float(ref["mean"]) - mean
        delta = float(rule["drop_delta"])
        cond = drop > delta
        if st["active"]:
            if drop < delta * float(rule.get("clear_fraction", 0.5)):
                st["consec"] = 0
                self._resolve(rule, now, f"caída {drop:.3f} < {delta * float(rule.get('clear_fraction', 0.5)):.3f}")
                self._log(rule, now, OK, n, drop, "resuelta")
            else:
                self._log(rule, now, FIRING, n, drop, "activa")
            return None
        st["consec"] = st["consec"] + 1 if cond else 0
        if cond and st["consec"] >= int(rule["sustain_events"]):
            reason = (
                f"La confianza media reciente ({mean:.3f}, n={n}) cayó {drop:.3f} por debajo de la "
                f"referencia ({ref['mean']:.3f}); delta configurado {delta}, sostenida durante "
                f"{st['consec']} evaluaciones consecutivas"
            )
            self._log(rule, now, FIRING, n, drop, "disparada")
            return self._fire(
                rule, now, reason, win,
                {"recent_mean": mean, "reference_mean": ref["mean"], "drop": drop, "consecutive": st["consec"], "n": n},
            )
        self._log(rule, now, PENDING if cond else OK, n, drop, f"consec={st['consec']}")
        return None

    def _eval_error_rate(self, rule, now):
        n_req = int(rule["window_events"])
        win = list(self.attempts)[-n_req:]
        n = len(win)
        if n < int(rule["min_samples"]):
            self._log(rule, now, INSUFFICIENT, n, None, f"{n} < min_samples={rule['min_samples']}")
            return None
        errs = sum(1 for w in win if w[4] == STATUS_INFERENCE_ERROR)
        rate = errs / n
        st = self.state[rule["id"]]
        if st["active"]:
            if rate < float(rule["clear_rate"]):
                self._resolve(rule, now, f"tasa de error {rate:.2f} < {rule['clear_rate']}")
                self._log(rule, now, OK, n, rate, "resuelta")
            else:
                self._log(rule, now, FIRING, n, rate, "activa")
            return None
        if rate > float(rule["max_rate"]):
            reason = f"{errs} de {n} intentos de inferencia fallaron (tasa {rate:.2f} > {rule['max_rate']})"
            self._log(rule, now, FIRING, n, rate, "disparada")
            return self._fire(rule, now, reason, win, {"rate": rate, "errors": errs, "n": n})
        self._log(rule, now, OK, n, rate, "")
        return None

    def _eval_version(self, rule, now):
        """Versión reportada en los eventos distinta de la versión esperada (G6)."""
        n_req = int(rule["window_events"])
        win = list(self.versions)[-n_req:]
        n = len(win)
        st = self.state[rule["id"]]
        if not self.expected_version:
            self._log(rule, now, INSUFFICIENT, n, None, "model.expected_version no configurada")
            return None
        if n < int(rule["min_samples"]):
            self._log(rule, now, INSUFFICIENT, n, None, f"{n} < min_samples={rule['min_samples']}")
            return None
        bad = [w for w in win if w[2] != self.expected_version]
        share = len(bad) / n
        if st["active"]:
            if share < float(rule.get("clear_share", 0.0)) or share == 0:
                self._resolve(rule, now, "las versiones reportadas coinciden con la esperada")
                self._log(rule, now, OK, n, share, "resuelta")
            else:
                self._log(rule, now, FIRING, n, share, "activa")
            return None
        if share >= float(rule["fire_share"]):
            seen = sorted({w[2] for w in bad if w[2]})
            reason = (f"{len(bad)} de los últimos {n} eventos reportan versión {seen} distinta de la esperada "
                      f"'{self.expected_version}'")
            self._log(rule, now, FIRING, n, share, "disparada")
            return self._fire(rule, now, reason, win, {"share": share, "reported": seen,
                                                      "expected": self.expected_version, "n": n})
        self._log(rule, now, OK, n, share, "")
        return None

    def _eval_stale(self, rule, now, last_frame_epoch):
        st = self.state[rule["id"]]
        max_age = float(rule["max_age_s"])
        ref_t = last_frame_epoch if last_frame_epoch is not None else self.run_start
        age = now - ref_t
        if last_frame_epoch is None and age < max_age:
            self._log(rule, now, INSUFFICIENT, 0, age, "aún no se ha recibido ningún frame")
            return None
        if age > max_age:
            if st["active"]:
                self._log(rule, now, FIRING, 1, age, "activa")
                return None
            what = "desde el último frame válido" if last_frame_epoch is not None else "desde el inicio del run"
            reason = f"Sin frames válidos durante {age:.1f}s {what} (máximo permitido {max_age}s)"
            self._log(rule, now, FIRING, 1, age, "disparada")
            win = [(self.last_event_id, ref_t, None, None, None)] if self.last_event_id else []
            return self._fire(rule, now, reason, win, {"age_s": age, "max_age_s": max_age}, start=ref_t)
        if st["active"]:
            self._resolve(rule, now, f"frames recuperados (antigüedad {age:.1f}s <= {max_age}s)")
        self._log(rule, now, OK, 1, age, "")
        return None

    # ----------------------------------------------------------- utilidades
    def _log(self, rule, now, outcome, n, value, detail):
        st = self.state[rule["id"]]
        if outcome == st["last_outcome"] and now - st["last_log"] < self.log_every:
            return
        st["last_outcome"] = outcome
        st["last_log"] = now
        db.insert(
            self.conn,
            "rule_evaluations",
            {"run_id": self.run_id, "rule_id": rule["id"], "ts": now, "outcome": outcome,
             "n_samples": n, "value": value, "detail": detail},
        )

    def _fire(self, rule, now, reason, window, observation, start: float | None = None):
        self.n_alerts += 1
        alert_id = f"A-{self.run_id}-{self.n_alerts:04d}"
        w_start = start if start is not None else (window[0][1] if window else now)
        row = {
            "alert_id": alert_id,
            "run_id": self.run_id,
            "rule_id": rule["id"],
            "rule_type": rule["type"],
            "rule_json": db.jdump(rule),
            "config_hash": self.config_hash,
            "fired_at": db.utc_iso(now),
            "fired_epoch": now,
            "severity": rule["severity"],
            "reason": reason,
            "suggested_action": rule["action"],
            "status": "active",
            "window_start_epoch": w_start,
            "window_end_epoch": now,
            "observation_json": db.jdump(observation),
        }
        db.insert(self.conn, "alerts", row)
        for w in window:
            if w[0]:
                self.conn.execute(
                    "INSERT OR IGNORE INTO alert_events(alert_id, event_id) VALUES (?, ?)", (alert_id, w[0])
                )
        self.state[rule["id"]]["active"] = alert_id
        return row

    def _resolve(self, rule, now, why):
        st = self.state[rule["id"]]
        alert_id = st["active"]
        if not alert_id:
            return
        self.conn.execute(
            "UPDATE alerts SET status='resolved', resolved_at=?, resolved_epoch=?, "
            "observation_json=json_set(COALESCE(observation_json,'{}'), '$.resolved_reason', ?) WHERE alert_id=?",
            (db.utc_iso(now), now, why, alert_id),
        )
        st["active"] = None
