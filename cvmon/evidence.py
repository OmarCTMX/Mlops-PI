"""Generación de evidencia por escenario: exportación, recálculo, verificaciones y resumen."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from . import db
from .config import ROOT
from .export import export_jsonl
from .model import sha256_file
from .recalc import format_report, recalc_run


def _rel(p: Path | str) -> str:
    """Ruta relativa al repositorio (portable); absoluta solo si queda fuera de él."""
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def replay_check(data_dir: str | Path, orig_run: str, replay_run: str, tol: float = 1e-6) -> dict[str, Any]:
    """Compara las confianzas de un run original con su reproducción desde las entradas guardadas."""
    conn = db.open_db(Path(data_dir) / "cvmon.db")
    q = "SELECT seq, pred_label, confidence FROM events WHERE run_id=? AND status='ok' ORDER BY seq"
    a = conn.execute(q, (orig_run,)).fetchall()
    b = conn.execute(q, (replay_run,)).fetchall()
    n = min(len(a), len(b))
    diffs = [abs(a[i]["confidence"] - b[i]["confidence"]) for i in range(n)]
    same_label = sum(1 for i in range(n) if a[i]["pred_label"] == b[i]["pred_label"])
    return {"original_n": len(a), "replay_n": len(b), "compared": n, "max_abs_diff": max(diffs) if diffs else None,
            "same_label": same_label, "identical": bool(n) and len(a) == len(b) and max(diffs) <= tol and same_label == n}


def _check(cid: str, desc: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"id": cid, "description": desc, "passed": bool(ok), "detail": detail}


def verify_run(conn, data_dir: Path, run_id: str, kind: str, recalc_rows: list[dict[str, Any]],
               model_path: Path | None = None) -> list[dict[str, Any]]:
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    ev = db.query(conn, "SELECT * FROM events WHERE run_id=? ORDER BY seq", (run_id,))
    ok = [e for e in ev if e["status"] == "ok"]
    alerts = db.query(conn, "SELECT * FROM alerts WHERE run_id=? ORDER BY fired_epoch", (run_id,))
    checks: list[dict[str, Any]] = []

    ident_ok = True
    detail = f"sha256 del run {run['model_sha256'][:12]}…"
    if model_path and model_path.is_file():
        ident_ok = sha256_file(model_path) == run["model_sha256"]
        detail += " coincide con el archivo del repo" if ident_ok else " NO coincide con el archivo del repo"
    checks.append(_check("V1", "Inferencias reales atribuibles a un modelo identificado", bool(ok) and ident_ok,
                         f"{len(ok)} inferencias ok; {detail}"))

    consistent = 0
    for e in ok:
        top = json.loads(e["topk_json"] or "[]")
        if top and abs(top[0]["score"] - e["confidence"]) < 1e-5 and top[0]["label"] == e["pred_label"]:
            consistent += 1
    checks.append(_check("V2", "Confianza y clase coinciden con la salida top-k del modelo (no inyectadas)",
                         bool(ok) and consistent == len(ok), f"{consistent}/{len(ok)} eventos consistentes"))

    caps = [e for e in ev if e["capture_path"]]
    present = sum(1 for e in caps if (data_dir / e["capture_path"]).is_file())
    checks.append(_check("V3", "Capturas vinculadas existen en disco (sin expiración automática)",
                         bool(caps) and present == len(caps), f"{present}/{len(caps)} capturas resuelven"))

    linked_ok = True
    for a in alerts:
        n = conn.execute("SELECT COUNT(*) c FROM alert_events WHERE alert_id=?", (a["alert_id"],)).fetchone()["c"]
        cfg = conn.execute("SELECT 1 FROM config_snapshots WHERE config_hash=?", (a["config_hash"],)).fetchone()
        if not (a["rule_json"] and cfg and a["suggested_action"] and a["reason"] and a["severity"]):
            linked_ok = False
        if n == 0 and a["rule_type"] != "stream_stale":
            linked_ok = False
    checks.append(_check("V4", "Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción",
                         linked_ok, f"{len(alerts)} alertas"))

    checks.append(_check("V5", "Métricas recalculadas de forma independiente coinciden con las almacenadas",
                         bool(recalc_rows) and all(r["match"] for r in recalc_rows),
                         f"{sum(1 for r in recalc_rows if r['match'])}/{len(recalc_rows)}"))

    zones = {z: sum(1 for e in ok if e["zone"] == z) for z in ("accepted", "doubt", "low")}
    evals = db.query(conn, "SELECT outcome, COUNT(*) n FROM rule_evaluations WHERE run_id=? GROUP BY outcome", (run_id,))
    checks.append(_check("V6", "Las reglas registraron evaluaciones (incluida la evidencia insuficiente)",
                         len(evals) > 0, ", ".join(f"{r['outcome']}={r['n']}" for r in evals)))

    if kind == "C1":
        checks.append(_check("C1.a", "Operación normal: hay inferencias suficientes (>= 20) y zona aceptada observada",
                             len(ok) >= 20 and zones["accepted"] > 0, f"ok={len(ok)} zonas={zones}"))
        low_share = zones["low"] / len(ok) if ok else 1
        checks.append(_check("C1.b", "Operación normal: la baja confianza no domina (< 20 % de las inferencias)",
                             low_share < 0.20, f"baja={low_share:.2f}"))
        lowc = [a for a in alerts if a["rule_id"] == "R-LOWCONF"]
        checks.append(_check("C1.c", "Sin alerta de baja confianza durante la operación normal",
                             not lowc, f"{len(lowc)} alertas R-LOWCONF"))
    elif kind == "C2":
        lows = [e for e in ok if e["zone"] == "low"]
        low_caps = [e for e in lows if e["capture_path"]]
        checks.append(_check("C2.a", "Hay inferencias reales en zona de baja confianza (>= 6)", len(lows) >= 6,
                             f"{len(lows)} eventos low"))
        checks.append(_check("C2.b", "Las capturas de baja confianza se conservaron y están vinculadas",
                             bool(lows) and len(low_caps) == len(lows), f"{len(low_caps)}/{len(lows)}"))
        lowc = [a for a in alerts if a["rule_id"] == "R-LOWCONF"]
        checks.append(_check("C2.c", "La alerta R-LOWCONF se generó según su regla declarada y enlaza eventos low",
                             bool(lowc) and all(
                                 conn.execute("SELECT COUNT(*) c FROM alert_events ae JOIN events e ON e.event_id=ae.event_id "
                                              "WHERE ae.alert_id=? AND e.zone='low'", (a["alert_id"],)).fetchone()["c"] >= 1
                                 for a in lowc), f"{len(lowc)} alertas"))
    elif kind == "S1":
        stale = [a for a in alerts if a["rule_id"] == "R-STALE"]
        obs = {r["kind"]: r["n"] for r in conn.execute(
            "SELECT kind, COUNT(*) n FROM stream_obs WHERE run_id=? GROUP BY kind", (run_id,))}
        checks.append(_check("S1.a", "Se detectó la interrupción (alerta R-STALE)", bool(stale), f"{len(stale)} alertas"))
        checks.append(_check("S1.b", "Hubo fallos de lectura e intentos de reconexión",
                             obs.get("read_fail", 0) > 0 and obs.get("reconnect_attempt", 0) > 0, str(obs)))
        checks.append(_check("S1.c", "La fuente se recuperó (reconnect_ok) y la alerta se resolvió",
                             obs.get("reconnect_ok", 0) > 0 and all(a["status"] == "resolved" for a in stale) and bool(stale),
                             f"reconnect_ok={obs.get('reconnect_ok', 0)}"))
        last_t = stale[0]["resolved_epoch"] if stale and stale[0]["resolved_epoch"] else None
        after = [e for e in ok if last_t and e["processed_epoch"] > last_t]
        checks.append(_check("S1.d", "Verificación posterior: hay inferencias reales tras la recuperación", len(after) >= 3,
                             f"{len(after)} inferencias posteriores"))
    elif kind == "S2":
        shift = [a for a in alerts if a["rule_id"] == "R-SHIFT"]
        checks.append(_check("S2.a", "Se disparó la regla de cambio sostenido R-SHIFT", bool(shift), f"{len(shift)} alertas"))
        ref_ok = False
        if shift:
            obsd = json.loads(shift[0]["observation_json"] or "{}")
            ref_ok = obsd.get("consecutive", 0) >= 1 and obsd.get("drop", 0) > 0
        checks.append(_check("S2.b", "La alerta registra la caída frente a la referencia y la persistencia", ref_ok, ""))
        before = [e for e in ok if shift and e["processed_epoch"] < shift[0]["fired_epoch"]]
        checks.append(_check("S2.c", "Hubo evidencia suficiente previa (no se disparó con datos insuficientes)",
                             len(before) >= 10, f"{len(before)} inferencias previas"))
    elif kind == "S4":
        ver = [a for a in alerts if a["rule_id"] == "R-VERSION"]
        checks.append(_check("S4.a", "Se detectó la versión distinta de la esperada (alerta R-VERSION)", bool(ver),
                             f"{len(ver)} alertas"))
        exp = json.loads(conn.execute("SELECT config_json FROM config_snapshots WHERE config_hash=?",
                                      (run["config_hash"],)).fetchone()["config_json"])["model"]["expected_version"]
        mism = sum(1 for e in ev if e["model_version"] != exp)
        checks.append(_check("S4.b", "Todos los eventos reportan una versión distinta de la esperada",
                             bool(ev) and mism == len(ev), f"esperada={exp}, reportada={run['model_version']}, {mism}/{len(ev)}"))
        base = conn.execute("SELECT DISTINCT model_sha256 FROM runs WHERE scenario IN ('C1','C2','REF')").fetchall()
        differs = bool(base) and all(b[0] != run["model_sha256"] for b in base)
        checks.append(_check("S4.c", "El artefacto desplegado es realmente otro (sha256 distinto al de C1/C2/REF)", differs,
                             f"sha256 S4 {run['model_sha256'][:12]}…"))
        g6 = [r for r in recalc_rows if r["metric_id"] == "G6_version_match_share"]
        checks.append(_check("S4.d", "La métrica G6 refleja la discrepancia (proporción 0)",
                             bool(g6) and g6[0]["recalculated"] == 0.0, str(g6[0]["recalculated"] if g6 else None)))
    elif kind == "S3":
        inv = [e for e in ev if e["status"] == "invalid_input"]
        checks.append(_check("S3.a", "Se registraron entradas inválidas sin detener el pipeline", bool(inv) and bool(ok),
                             f"invalid={len(inv)}, ok={len(ok)}"))
        checks.append(_check("S3.b", "Las entradas inválidas no tienen puntuación ni zona (estado aparte)",
                             all(e["confidence"] is None and e["zone"] is None for e in inv), ""))
    return checks


def finalize(data_dir: str | Path, run_id: str, out_dir: str | Path, kind: str = "generic",
             model_path: str | Path | None = None, inputs_dir: str | Path | None = None) -> dict[str, Any]:
    data_dir = Path(data_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    conn = db.open_db(data_dir / "cvmon.db")
    run = conn.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        raise SystemExit(f"No existe el run {run_id}")
    exp_dir = out / "exports"
    counts = export_jsonl(conn, exp_dir, [run_id])
    ref = Path("config/reference.json")
    if ref.is_file():
        shutil.copyfile(ref, exp_dir / "reference.json")
    rows = recalc_run(exp_dir, data_dir, run_id)
    recalc_txt = format_report(run_id, rows)
    (out / "recalc.txt").write_text(recalc_txt + "\n", encoding="utf-8")
    checks = verify_run(conn, data_dir, run_id, kind, rows, Path(model_path) if model_path else None)
    (out / "verification.json").write_text(json.dumps(checks, indent=2, ensure_ascii=False), encoding="utf-8")

    ev = db.query(conn, "SELECT * FROM events WHERE run_id=? ORDER BY seq", (run_id,))
    alerts = db.query(conn, "SELECT * FROM alerts WHERE run_id=? ORDER BY fired_epoch", (run_id,))
    zones: dict[str, int] = {}
    for e in ev:
        zones[e["zone"] or e["status"]] = zones.get(e["zone"] or e["status"], 0) + 1
    L = [f"# Evidencia · {out.name} · run `{run_id}`", "",
         "## Identidad de la ejecución", "",
         f"- Escenario: `{run['scenario']}`  · inicio {run['started_at']} · fin {run['ended_at']}",
         f"- Commit del código: `{run['git_commit']}`" + (" (árbol con cambios sin confirmar al ejecutar)" if run["git_dirty"] else ""),
         f"- Configuración: hash `{run['config_hash']}` (copia en `exports/config_snapshots.jsonl`)",
         f"- Fuente: `{run['source_id']}` ({run['source_type']})",
         f"- Modelo: `{run['model_id']}` / `{run['model_version']}` sha256 `{run['model_sha256']}`",
         f"- Notas: {run['notes'] or '-'}", "",
         "## Resultados", "",
         f"- Eventos: {len(ev)} · por zona/estado: {json.dumps(zones, ensure_ascii=False)}",
         f"- Alertas: {len(alerts)}", "",
         "| Alerta | Regla | Severidad | Estado | Motivo |", "| --- | --- | --- | --- | --- |"]
    for a in alerts:
        L.append(f"| `{a['alert_id']}` | {a['rule_id']} | {a['severity']} | {a['status']} | {a['reason']} |")
    L += ["", "## Verificaciones automáticas", "", "| ID | Verificación | Resultado | Detalle |", "| --- | --- | --- | --- |"]
    for c in checks:
        L.append(f"| {c['id']} | {c['description']} | {'PASA' if c['passed'] else 'FALLA'} | {c['detail']} |")
    L += ["", "## Cadena de una muestra (fuente → modelo → evento → captura → alerta)", ""]
    sample_alert = alerts[0] if alerts else None
    if sample_alert:
        linked = db.query(conn, "SELECT e.* FROM events e JOIN alert_events ae ON e.event_id=ae.event_id "
                                "WHERE ae.alert_id=? ORDER BY e.seq", (sample_alert["alert_id"],))
        L.append(f"Alerta `{sample_alert['alert_id']}` (regla {sample_alert['rule_id']}, config `{sample_alert['config_hash']}`):")
        for e in linked[:5]:
            cap = e["capture_path"]
            exists = (data_dir / cap).is_file() if cap else None
            L.append(f"- evento `{e['event_id']}` · {e['pred_label']} {e['confidence'] if e['confidence'] is None else round(e['confidence'], 4)} "
                     f"· zona {e['zone']} · captura `{_rel(data_dir / cap) if cap else '-'}` · existe: {exists}")
    elif ev:
        e = ev[0]
        L.append(f"Evento `{e['event_id']}` · {e['pred_label']} {e['confidence']} · zona {e['zone']} · captura `{e['capture_path']}`")
    else:
        L.append("(sin eventos)")
    L += ["", "## Recálculo independiente de métricas", "", "```", recalc_txt, "```", "",
          "## Archivos", "",
          "- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)",
          f"- Capturas: `{_rel(data_dir / 'captures' / run_id)}/`",
          "- `recalc.txt`, `verification.json`: salidas de los comandos de verificación"]
    if inputs_dir:
        L.append(f"- Entradas reproducibles (bytes originales de la fuente): `{_rel(inputs_dir)}`")
    (out / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    return {"counts": counts, "checks": checks, "recalc": rows}
