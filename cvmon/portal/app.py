"""Portal web: consulta de eventos y alertas (base) + dashboard, stream, filtros, exportación y revisión (extras)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import db
from ..config import ROOT, load_config, resolve
from ..export import rows_to_csv
from ..metrics import BASE_METRICS, EXTRA_METRICS

HERE = Path(__file__).resolve().parent
PAGE_SIZE = 50

METRIC_DOCS = {
    "G1_inference_ms_p95": "Percentil 95 (y p50) del tiempo de session.run del modelo, en ms. Población: eventos con status=ok.",
    "G2_processing_fps": "(n-1)/(t_último-t_primero) de processed_epoch en eventos ok. Requiere n>=2.",
    "G3_process_rss_mb": "Media de la memoria residente (RSS) del proceso de inferencia, muestreada cada 2 s (psutil).",
    "G4_low_conf_share": "Eventos con zona 'low' entre eventos con puntuación (status=ok).",
    "G5_trace_coverage": "Eventos con todos los campos obligatorios, config_hash resoluble y captura existente en disco, entre todos los eventos.",
    "G6_version_match_share": "Eventos cuyo model_version reportado coincide con model.expected_version de su configuración.",
    "G7_active_alerts": "Alertas fired_at<=T y no resueltas en T.",
    "X1_capture_fps": "(n-1)/(t_último-t_primero) de frames capturados (stream_obs.kind=captured).",
    "X2_dropped_share": "Frames descartados por la aplicación entre capturados, separados por motivo (sampling | saturation).",
    "X3_process_cpu_pct": "Media del % de CPU del proceso (psutil; puede superar 100 con varios hilos).",
    "X4_e2e_ms_p95": "Percentil 95 de captura->resultado, con desglose de cola, preprocesamiento e inferencia.",
    "X5_confidence_psi": "PSI entre la distribución de confianza del run y la de la referencia (10 bins, eps=1e-4). Requiere >=30 muestras.",
    "X6_invalid_input_rate": "Eventos invalid_input entre todos los eventos.",
}


def create_app(data_dir: str | Path = "data", config_path: str = "config/config.yaml") -> FastAPI:
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    cfg = load_config(config_path)
    db.open_db(data_dir / "cvmon.db").close()
    app = FastAPI(title="Centro de monitoreo de computer vision", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(HERE / "templates"))
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
    (data_dir / "captures").mkdir(exist_ok=True)
    app.mount("/captures", StaticFiles(directory=str(data_dir / "captures")), name="captures")

    def conn():
        return db.connect(data_dir / "cvmon.db")

    def render(request: Request, name: str, ctx: dict[str, Any], status: int = 200):
        ctx = {"cfg": cfg, "student": cfg.get("project", {}).get("student", ""), **ctx}
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    def err(request: Request, msg: str, status: int = 400):
        return render(request, "error.html", {"message": msg, "status": status}, status)

    templates.env.filters["ts"] = lambda e: db.utc_iso(e) if e else "-"
    templates.env.filters["f3"] = lambda v: "-" if v is None else f"{v:.3f}"
    templates.env.filters["f1"] = lambda v: "-" if v is None else f"{v:.1f}"

    # ------------------------------------------------------------ filtros
    def parse_filters(q: dict[str, str]) -> tuple[str, list[Any], dict[str, str]]:
        where, params, clean = [], [], {}
        for key in ("run", "zone", "status", "source", "model_version"):
            v = (q.get(key) or "").strip()
            if v:
                col = {"run": "e.run_id", "zone": "e.zone", "status": "e.status", "source": "e.source_id",
                       "model_version": "e.model_version"}[key]
                where.append(f"{col} = ?")
                params.append(v)
                clean[key] = v
        label = (q.get("label") or "").strip()
        if label:
            where.append("e.pred_label LIKE ?")
            params.append(f"%{label}%")
            clean["label"] = label
        for key, op, col in (("min_conf", ">=", "e.confidence"), ("max_conf", "<=", "e.confidence")):
            v = (q.get(key) or "").strip()
            if v:
                try:
                    fv = float(v)
                except ValueError:
                    raise ValueError(f"'{key}' debe ser un número entre 0 y 1")
                if not 0.0 <= fv <= 1.0:
                    raise ValueError(f"'{key}' debe estar entre 0 y 1")
                where.append(f"{col} {op} ?")
                params.append(fv)
                clean[key] = v
        for key, op in (("since", ">="), ("until", "<=")):
            v = (q.get(key) or "").strip()
            if v:
                try:
                    t = time.mktime(time.strptime(v, "%Y-%m-%dT%H:%M")) if "T" in v else time.mktime(time.strptime(v, "%Y-%m-%d"))
                except ValueError:
                    raise ValueError(f"'{key}' debe tener formato AAAA-MM-DD o AAAA-MM-DDTHH:MM")
                where.append(f"e.captured_epoch {op} ?")
                params.append(t)
                clean[key] = v
        if (q.get("with_capture") or "") == "1":
            where.append("e.capture_path IS NOT NULL")
            clean["with_capture"] = "1"
        if (q.get("alerted") or "") == "1":
            where.append("e.event_id IN (SELECT event_id FROM alert_events)")
            clean["alerted"] = "1"
        return (" WHERE " + " AND ".join(where)) if where else "", params, clean

    def event_rows(c, q, limit=None, offset=0):
        w, p, clean = parse_filters(q)
        total = c.execute(f"SELECT COUNT(*) n FROM events e{w}", p).fetchone()["n"]
        sql = (f"SELECT e.*, (SELECT COUNT(*) FROM alert_events ae WHERE ae.event_id=e.event_id) n_alerts "
               f"FROM events e{w} ORDER BY e.captured_epoch DESC, e.seq DESC")
        if limit is not None:
            sql += f" LIMIT {int(limit)} OFFSET {int(offset)}"
        return db.query(c, sql, p), total, clean

    # ----------------------------------------------------------- páginas
    @app.get("/health")
    def health():
        return {"status": "ok", "time": db.utc_iso()}

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, run: str = ""):
        c = conn()
        try:
            runs = db.query(c, "SELECT * FROM runs ORDER BY started_epoch DESC")
            sel = run or (runs[0]["run_id"] if runs else "")
            kpi: dict[str, Any] = {}
            if sel:
                kpi["events"] = c.execute("SELECT COUNT(*) n FROM events WHERE run_id=?", (sel,)).fetchone()["n"]
                kpi["zones"] = {r["zone"] or "sin_puntuacion": r["n"] for r in db.query(
                    c, "SELECT zone, COUNT(*) n FROM events WHERE run_id=? GROUP BY zone", (sel,))}
                kpi["alerts_active"] = c.execute(
                    "SELECT COUNT(*) n FROM alerts WHERE run_id=? AND status='active'", (sel,)).fetchone()["n"]
                kpi["alerts_total"] = c.execute("SELECT COUNT(*) n FROM alerts WHERE run_id=?", (sel,)).fetchone()["n"]
                kpi["captures"] = c.execute(
                    "SELECT COUNT(*) n FROM events WHERE run_id=? AND capture_path IS NOT NULL", (sel,)).fetchone()["n"]
            recent_alerts = db.query(c, "SELECT * FROM alerts" + (" WHERE run_id=?" if sel else "") +
                                     " ORDER BY fired_epoch DESC LIMIT 5", [sel] if sel else [])
            return render(request, "home.html", {"runs": runs, "sel": sel, "kpi": kpi, "recent_alerts": recent_alerts})
        finally:
            c.close()

    @app.get("/events", response_class=HTMLResponse)
    def events(request: Request, page: int = 1):
        q = dict(request.query_params)
        c = conn()
        try:
            page = max(1, page)
            try:
                rows, total, clean = event_rows(c, q, PAGE_SIZE, (page - 1) * PAGE_SIZE)
            except ValueError as exc:
                return err(request, str(exc))
            runs = db.query(c, "SELECT run_id FROM runs ORDER BY started_epoch DESC")
            sources = [r[0] for r in c.execute("SELECT DISTINCT source_id FROM events")]
            versions = [r[0] for r in c.execute("SELECT DISTINCT model_version FROM events")]
            qs = urlencode(clean)
            return render(request, "events.html", {
                "rows": rows, "total": total, "page": page, "pages": max(1, -(-total // PAGE_SIZE)),
                "f": clean, "runs": runs, "sources": sources, "versions": versions, "qs": qs})
        finally:
            c.close()

    @app.get("/events/{event_id}", response_class=HTMLResponse)
    def event_detail(request: Request, event_id: str):
        c = conn()
        try:
            e = c.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
            if not e:
                return err(request, f"No existe el evento {event_id}", 404)
            alerts = db.query(c, "SELECT a.* FROM alerts a JOIN alert_events ae ON a.alert_id=ae.alert_id "
                                 "WHERE ae.event_id=? ORDER BY a.fired_epoch", (event_id,))
            run = c.execute("SELECT * FROM runs WHERE run_id=?", (e["run_id"],)).fetchone()
            snap = c.execute("SELECT config_json FROM config_snapshots WHERE config_hash=?", (e["config_hash"],)).fetchone()
            review = c.execute("SELECT * FROM reviews WHERE event_id=?", (event_id,)).fetchone()
            prev = c.execute("SELECT event_id FROM events WHERE run_id=? AND seq<? ORDER BY seq DESC LIMIT 1",
                             (e["run_id"], e["seq"])).fetchone()
            nxt = c.execute("SELECT event_id FROM events WHERE run_id=? AND seq>? ORDER BY seq LIMIT 1",
                            (e["run_id"], e["seq"])).fetchone()
            return render(request, "event_detail.html", {
                "e": e, "alerts": alerts, "run": run, "review": review,
                "topk": json.loads(e["topk_json"]) if e["topk_json"] else [],
                "config_json": json.dumps(json.loads(snap["config_json"]), indent=2, ensure_ascii=False) if snap else None,
                "prev": prev, "next": nxt})
        finally:
            c.close()

    @app.get("/alerts", response_class=HTMLResponse)
    def alerts(request: Request, run: str = "", severity: str = "", status: str = "", rule: str = ""):
        c = conn()
        try:
            where, params = [], []
            for col, v in (("run_id", run), ("severity", severity), ("status", status), ("rule_id", rule)):
                if v:
                    where.append(f"{col}=?")
                    params.append(v)
            w = (" WHERE " + " AND ".join(where)) if where else ""
            rows = db.query(c, f"SELECT a.*, (SELECT COUNT(*) FROM alert_events ae WHERE ae.alert_id=a.alert_id) n_events "
                               f"FROM alerts a{w} ORDER BY fired_epoch DESC", params)
            runs = db.query(c, "SELECT run_id FROM runs ORDER BY started_epoch DESC")
            rules = [r[0] for r in c.execute("SELECT DISTINCT rule_id FROM alerts")]
            return render(request, "alerts.html", {
                "rows": rows, "runs": runs, "rules": rules,
                "f": {"run": run, "severity": severity, "status": status, "rule": rule}})
        finally:
            c.close()

    @app.get("/alerts/{alert_id}", response_class=HTMLResponse)
    def alert_detail(request: Request, alert_id: str):
        c = conn()
        try:
            a = c.execute("SELECT * FROM alerts WHERE alert_id=?", (alert_id,)).fetchone()
            if not a:
                return err(request, f"No existe la alerta {alert_id}", 404)
            events_ = db.query(c, "SELECT e.* FROM events e JOIN alert_events ae ON e.event_id=ae.event_id "
                                  "WHERE ae.alert_id=? ORDER BY e.seq", (alert_id,))
            evals = db.query(c, "SELECT * FROM rule_evaluations WHERE run_id=? AND rule_id=? AND ts<=? "
                                "ORDER BY ts DESC LIMIT 15", (a["run_id"], a["rule_id"], a["fired_epoch"] + 1))
            return render(request, "alert_detail.html", {
                "a": a, "events": events_, "evals": list(reversed(evals)),
                "rule": json.loads(a["rule_json"]), "obs": json.loads(a["observation_json"] or "{}")})
        finally:
            c.close()

    @app.get("/runs", response_class=HTMLResponse)
    def runs_page(request: Request):
        c = conn()
        try:
            rows = db.query(c, "SELECT r.*, (SELECT COUNT(*) FROM events e WHERE e.run_id=r.run_id) n_events, "
                               "(SELECT COUNT(*) FROM alerts a WHERE a.run_id=r.run_id) n_alerts "
                               "FROM runs r ORDER BY started_epoch DESC")
            return render(request, "runs.html", {"rows": rows})
        finally:
            c.close()

    @app.get("/runs/{run_id}", response_class=HTMLResponse)
    def run_detail(request: Request, run_id: str):
        c = conn()
        try:
            r = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if not r:
                return err(request, f"No existe el run {run_id}", 404)
            snap = c.execute("SELECT config_json FROM config_snapshots WHERE config_hash=?", (r["config_hash"],)).fetchone()
            evals = db.query(c, "SELECT rule_id, outcome, COUNT(*) n FROM rule_evaluations WHERE run_id=? "
                                "GROUP BY rule_id, outcome ORDER BY rule_id, outcome", (run_id,))
            obs = db.query(c, "SELECT kind, COALESCE(reason,'') reason, COUNT(*) n FROM stream_obs WHERE run_id=? "
                              "GROUP BY kind, reason ORDER BY kind", (run_id,))
            return render(request, "run_detail.html", {
                "r": r, "ident": json.loads(r["model_identity_json"]),
                "config_json": json.dumps(json.loads(snap["config_json"]), indent=2, ensure_ascii=False) if snap else "",
                "evals": evals, "obs": obs})
        finally:
            c.close()

    @app.get("/metrics", response_class=HTMLResponse)
    def metrics_page(request: Request, run: str = ""):
        c = conn()
        try:
            runs = db.query(c, "SELECT run_id FROM runs ORDER BY started_epoch DESC")
            sel = run or (runs[0]["run_id"] if runs else "")
            rows = []
            if sel:
                rows = db.query(c, "SELECT m.* FROM metric_samples m JOIN (SELECT metric_id, MAX(ts) t FROM metric_samples "
                                   "WHERE run_id=? GROUP BY metric_id) x ON m.metric_id=x.metric_id AND m.ts=x.t "
                                   "WHERE m.run_id=? ORDER BY m.metric_id", (sel, sel))
            items = []
            for r in rows:
                base = r["metric_id"] in BASE_METRICS
                desc = (BASE_METRICS.get(r["metric_id"]) or EXTRA_METRICS.get(r["metric_id"]) or ("", ""))[1]
                items.append({"r": r, "base": base, "desc": desc, "doc": METRIC_DOCS.get(r["metric_id"], ""),
                              "detail": json.loads(r["detail"] or "{}")})
            return render(request, "metrics.html", {"runs": runs, "sel": sel, "items": items})
        finally:
            c.close()

    @app.get("/live", response_class=HTMLResponse)
    def live(request: Request):
        return render(request, "live.html", {})

    @app.get("/live/latest.jpg")
    def live_img():
        p = data_dir / "live" / "latest.jpg"
        if not p.is_file():
            raise HTTPException(404, "Aún no hay frames")
        return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/live")
    def live_meta():
        p = data_dir / "live" / "latest.json"
        if not p.is_file():
            return JSONResponse({"available": False})
        meta = json.loads(p.read_text(encoding="utf-8"))
        meta["available"] = True
        meta["age_s"] = time.time() - meta["captured_epoch"]
        return meta

    @app.get("/gallery", response_class=HTMLResponse)
    def gallery(request: Request, run: str = "", verdict: str = "", reason: str = ""):
        c = conn()
        try:
            where, params = ["e.capture_path IS NOT NULL"], []
            if run:
                where.append("e.run_id=?"); params.append(run)
            if reason:
                where.append("e.capture_reason=?"); params.append(reason)
            if verdict == "pending":
                where.append("r.event_id IS NULL")
            elif verdict in ("correct", "incorrect", "unsure"):
                where.append("r.verdict=?"); params.append(verdict)
            rows = db.query(c, "SELECT e.*, r.verdict, r.note FROM events e LEFT JOIN reviews r ON r.event_id=e.event_id "
                               "WHERE " + " AND ".join(where) + " ORDER BY e.captured_epoch DESC LIMIT 200", params)
            runs = db.query(c, "SELECT run_id FROM runs ORDER BY started_epoch DESC")
            return render(request, "gallery.html", {"rows": rows, "runs": runs,
                                                    "f": {"run": run, "verdict": verdict, "reason": reason}})
        finally:
            c.close()

    @app.post("/reviews")
    def review(event_id: str = Form(...), verdict: str = Form(...), note: str = Form(""), back: str = Form("/gallery")):
        if verdict not in ("correct", "incorrect", "unsure"):
            raise HTTPException(400, "Veredicto inválido")
        c = conn()
        try:
            if not c.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone():
                raise HTTPException(404, "Evento inexistente")
            c.execute("INSERT INTO reviews(event_id, verdict, note, reviewed_at) VALUES (?,?,?,?) "
                      "ON CONFLICT(event_id) DO UPDATE SET verdict=excluded.verdict, note=excluded.note, "
                      "reviewed_at=excluded.reviewed_at", (event_id, verdict, note[:500], db.utc_iso()))
        finally:
            c.close()
        if not back.startswith("/") or back.startswith("//"):
            back = "/gallery"
        return RedirectResponse(back, status_code=303)

    # ----------------------------------------------------------- API / export
    @app.get("/api/series")
    def series(run: str = ""):
        c = conn()
        try:
            if not run:
                r = c.execute("SELECT run_id FROM runs ORDER BY started_epoch DESC LIMIT 1").fetchone()
                run = r[0] if r else ""
            ev = db.query(c, "SELECT event_id, seq, captured_epoch, confidence, zone, status, inference_ms, e2e_ms "
                             "FROM events WHERE run_id=? ORDER BY seq", (run,))
            al = db.query(c, "SELECT alert_id, rule_id, severity, fired_epoch, resolved_epoch, status FROM alerts WHERE run_id=?", (run,))
            r = c.execute("SELECT config_json FROM config_snapshots WHERE config_hash=(SELECT config_hash FROM runs WHERE run_id=?)",
                          (run,)).fetchone()
            th = json.loads(r[0])["thresholds"] if r else cfg["thresholds"]
            ref = None
            rp = resolve(cfg.get("reference", {}).get("path", "config/reference.json"))
            if rp.is_file():
                ref = json.loads(rp.read_text(encoding="utf-8"))
            return {"run": run, "thresholds": th, "events": [dict(x) for x in ev], "alerts": [dict(x) for x in al],
                    "reference": {"hist_edges": ref["hist_edges"], "hist_props": ref["hist_props"], "mean": ref["mean"],
                                  "n": ref["n"]} if ref else None}
        finally:
            c.close()

    @app.get("/export/events.{fmt}")
    def export_events(request: Request, fmt: str):
        if fmt not in ("csv", "json"):
            raise HTTPException(404)
        c = conn()
        try:
            try:
                rows, total, _ = event_rows(c, dict(request.query_params))
            except ValueError as exc:
                raise HTTPException(400, str(exc))
            if fmt == "json":
                body = json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1)
                return Response(body, media_type="application/json",
                                headers={"Content-Disposition": 'attachment; filename="events.json"'})
            cols = ["event_id", "run_id", "seq", "frame_id", "task", "captured_at", "source_id", "model_id", "model_version", "config_hash",
                    "status", "zone", "pred_label", "confidence", "threshold_lower", "threshold_upper", "inference_ms",
                    "capture_path", "capture_reason", "n_alerts"]
            return Response(rows_to_csv(rows, cols) or ",".join(cols) + "\n", media_type="text/csv; charset=utf-8",
                            headers={"Content-Disposition": 'attachment; filename="events.csv"'})
        finally:
            c.close()

    @app.get("/export/alerts.{fmt}")
    def export_alerts(fmt: str):
        if fmt not in ("csv", "json"):
            raise HTTPException(404)
        c = conn()
        try:
            rows = db.query(c, "SELECT alert_id, run_id, rule_id, severity, fired_at, status, resolved_at, reason, "
                               "suggested_action, config_hash FROM alerts ORDER BY fired_epoch")
            if fmt == "json":
                return Response(json.dumps([dict(r) for r in rows], ensure_ascii=False, indent=1),
                                media_type="application/json",
                                headers={"Content-Disposition": 'attachment; filename="alerts.json"'})
            return Response(rows_to_csv(rows) or "alert_id\n", media_type="text/csv; charset=utf-8",
                            headers={"Content-Disposition": 'attachment; filename="alerts.csv"'})
        finally:
            c.close()

    return app
