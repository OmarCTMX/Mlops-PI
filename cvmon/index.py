"""Genera evidence/INDEX.md (criterio -> archivo/ID) y evidence/EXTRAS.md desde las evidencias reales.

Nada se declara como demostrado si no hay verificación que lo respalde: lo demás queda como PENDIENTE.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from . import db
from .config import ROOT

EVID = ROOT / "evidence"


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=15)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _checks(name: str) -> list[dict[str, Any]] | None:
    p = EVID / name / "verification.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def _passed(name: str, prefix: tuple[str, ...] | None = None) -> tuple[bool, str]:
    ch = _checks(name)
    if ch is None:
        return False, "sin evidencia (ejecutar el escenario)"
    sel = [c for c in ch if prefix is None or c["id"].startswith(prefix)]
    bad = [c["id"] for c in sel if not c["passed"]]
    return (not bad and bool(sel)), ("todas las verificaciones pasan" if not bad else f"fallan: {', '.join(bad)}")


def _metric(conn, scenario: str, metric_id: str) -> tuple[float | None, int | None, str | None]:
    r = conn.execute(
        "SELECT m.value, m.n, m.run_id FROM metric_samples m JOIN runs r ON r.run_id=m.run_id "
        "WHERE r.scenario=? AND m.metric_id=? ORDER BY r.started_epoch DESC, m.ts DESC LIMIT 1",
        (scenario, metric_id)).fetchone()
    return (r["value"], r["n"], r["run_id"]) if r else (None, None, None)


def build(data_dir: str | Path = "data") -> tuple[str, str]:
    data_dir = Path(data_dir)
    conn = db.open_db(data_dir / "cvmon.db")
    head = _git("rev-parse", "HEAD")
    runs = db.query(conn, "SELECT * FROM runs ORDER BY started_epoch")
    scen_dirs = sorted(p.name for p in EVID.iterdir() if p.is_dir() and (p / "verification.json").is_file()) if EVID.is_dir() else []

    # ------------------------------------------------------------------ INDEX
    L = ["# Índice de evidencias (criterio → archivo/ID)", "",
         "Generado con `python -m cvmon index`. Autoría individual: ver `README.md`.", "",
         "## Revisiones Git", "",
         f"- Commit actual del repositorio al generar este índice: `{head or 'desconocido'}`.",
         "- Cada `run` guarda en `runs.git_commit` el commit del **código** con el que se ejecutó (ver tabla de runs).",
         "- Las evidencias (`data/`, `evidence/`) se incorporan en un commit **posterior** al código probado;",
         "  el código no cambia entre ambos (el campo `git_dirty` indica si el árbol de código tenía cambios al ejecutar).", "",
         "## Runs de evidencia", "",
         "| Escenario | run_id | Commit del código | Config | Modelo | Verificaciones |", "| --- | --- | --- | --- | --- | --- |"]
    for r in runs:
        ok, det = _passed(r["scenario"]) if r["scenario"] in scen_dirs else (False, "-")
        L.append(f"| {r['scenario']} | `{r['run_id']}` | `{(r['git_commit'] or '-')[:10]}`{' (sucio)' if r['git_dirty'] else ''} | "
                 f"`{r['config_hash']}` | {r['model_version']} | {'PASA' if ok else det} |")
    if not runs:
        L.append("| (sin runs todavía) | | | | | |")

    L += ["", "## Rúbrica → evidencia", "", "| Criterio | Dónde está | Evidencia verificable |", "| --- | --- | --- |"]
    rows = [
        ("R1.1 fuente y muestreo", "`config/config.yaml` (source, sampling), `cvmon/source.py`, `cvmon/pipeline.py`, `docs/politica-confianza-y-alertas.md`", "`evidence/C1/exports/stream_obs.jsonl` (captured/dropped por motivo), métrica `X1_capture_fps`, `X2_dropped_share`"),
        ("R1.2 inferencia real", "`cvmon/model.py` (ONNX Runtime)", "verificaciones V1 y V2 en `evidence/*/verification.json` (confianza = top‑1 del modelo; sha256 del modelo); `replay_check.json` (mismas entradas ⇒ mismos scores)"),
        ("R1.3 identidad del modelo", "`models/MODEL_CARD.md`, `runs.model_identity_json`", "portal `/runs/<run_id>`; `evidence/*/exports/runs.jsonl`"),
        ("R2 métricas G1–G7", "`docs/inventario-metricas.md`, `cvmon/metrics.py`, `cvmon/recalc.py`", "`evidence/*/recalc.txt`; portal `/metrics`"),
        ("R3.1 umbrales y justificación", "`config/config.yaml` (thresholds), `cvmon/reference.py`", "`evidence/REF/threshold_justification.md`"),
        ("R3.2 tres zonas", "`cvmon/policy.py`, `tests/test_policy_config.py`", "`events.zone` en `evidence/*/exports/events.jsonl`; `/events?zone=…`"),
        ("R3.3 referencia, ventanas, cambio sostenido", "`config/reference.json`, `config/config.yaml` (R-SHIFT), `docs/politica-confianza-y-alertas.md`", "`rule_evaluations.jsonl` (incluye `insufficient_evidence`)"),
        ("R4.1 eventos", "`cvmon/db.py` (tabla events), `cvmon/pipeline.py`", "`evidence/*/exports/events.jsonl`"),
        ("R4.2 persistencia y consulta en portal", "`cvmon/portal/app.py`, `data/cvmon.db`", "`/events`, `/events/<id>`; `tests/test_portal.py`; capturas de pantalla en `evidence/portal/`"),
        ("R4.3 imágenes sin expiración", "`config/config.yaml` (capture), `data/captures/<run_id>/`", "verificación V3 (cada captura existe); no hay código de borrado/TTL"),
        ("R5.1 reglas", "`config/config.yaml` (alerts.rules), `cvmon/alerts.py`, `docs/politica-confianza-y-alertas.md`", "`tests/test_alerts.py`"),
        ("R5.2 alertas desde observaciones reales", "`cvmon/alerts.py`, tablas `alerts`/`alert_events`", "verificación V4; sección “Cadena de una muestra” de `evidence/*/summary.md`"),
        ("R5.3 alertas en el portal", "`/alerts`, `/alerts/<id>`", "capturas en `evidence/portal/`"),
        ("R6.1 C1 operación normal", "`scripts/scenario.ps1`, `docs/escenarios.md`", "`evidence/C1/` (summary.md, verification.json, exports, inputs, replay_check.json)"),
        ("R6.2 C2 baja confianza", "`scripts/scenario.ps1`, `docs/escenarios.md`", "`evidence/C2/` (ídem)"),
        ("R7.1 instalación y comandos", "`README.md`, `requirements.txt`, `scripts/`", "—"),
        ("R7.2 evidencias ligadas al commit", "este índice, tabla de runs", "`recalc.txt`, `replay_check.json`"),
        ("R7.3 autoría y procedencia", "`README.md`, `models/MODEL_CARD.md`", "—"),
    ]
    for a, b, c in rows:
        L.append(f"| {a} | {b} | {c} |")
    L += ["", "## Estado de C1/C2", ""]
    for name in ("C1", "C2"):
        ok, det = _passed(name)
        L.append(f"- {name}: {'**PASA**' if ok else '**PENDIENTE**'} — {det}")
    L += ["", "Inventario de extras reclamados: `evidence/EXTRAS.md`.", ""]

    # ----------------------------------------------------------------- EXTRAS
    E = ["# Extras reclamados (sin doble conteo con la base)", "",
         "Estado calculado por `python -m cvmon index` a partir de las verificaciones reales. "
         "“Pendiente” = aún sin evidencia que lo respalde; no se reclama.", ""]
    E += ["## Escenarios adicionales (S)", "", "| ID | Escenario | Nivel solicitado | Evidencia | Estado |", "| --- | --- | --- | --- | --- |"]
    for sid, title, pts, kind in (("S1", "Interrupción del stream y recuperación (fallo → alerta R‑STALE → reconexión → verificación posterior)", 10, "S1"),
                                  ("S2", "Cambio sostenido de confianza frente a la referencia (R‑SHIFT)", 8, "S2"),
                                  ("S3", "Entradas inválidas (imágenes corruptas) sin detener el pipeline", 5, "S3"),
                                  ("S4", "Cambio de versión del modelo (dos artefactos reales; alerta R‑VERSION)", 5, "S4")):
        ok, det = _passed(kind)
        E.append(f"| {sid} | {title} | {pts} | `evidence/{kind}/` | {'DEMOSTRADO' if ok else 'PENDIENTE'} — {det} |")
    E += ["", "Notas: C2 (baja confianza aislada) **no** se reclama como drift; S2 es otra secuencia con transición y persistencia.", ""]

    E += ["## Métricas adicionales (M)", "", "| ID | Métrica | Nivel | Valor (run de referencia) | Condición del nivel | Estado |", "| --- | --- | --- | --- | --- | --- |"]
    c1 = lambda m: _metric(conn, "C1", m)
    def fmt(t):
        return "-" if t[0] is None else f"{t[0]:.4g} (n={t[1]}, `{t[2]}`)"
    x1, x2, x3, x4 = c1("X1_capture_fps"), c1("X2_dropped_share"), c1("X3_process_cpu_pct"), c1("X4_e2e_ms_p95")
    psi_c1, psi_s2 = c1("X5_confidence_psi"), _metric(conn, "S2", "X5_confidence_psi")
    x6 = _metric(conn, "S3", "X6_invalid_input_rate")
    psi_ok = psi_c1[0] is not None and psi_s2[0] is not None and psi_c1[0] < 0.1 <= psi_s2[0]
    E.append(f"| M1 | `X1_capture_fps` FPS de captura | 5 | {fmt(x1)} | tasa derivada, recálculo comprobable | {'DEMOSTRADO' if x1[0] is not None else 'PENDIENTE'} |")
    E.append(f"| M2 | `X2_dropped_share` descartes por motivo | 5 | {fmt(x2)} | proporción con motivos separados | {'DEMOSTRADO' if x2[0] is not None else 'PENDIENTE'} |")
    E.append(f"| M3 | `X3_process_cpu_pct` CPU del proceso | 3 | {fmt(x3)} | agregado sencillo | {'DEMOSTRADO' if x3[0] is not None else 'PENDIENTE'} |")
    E.append(f"| M4 | `X4_e2e_ms_p95` latencia extremo a extremo | 5 | {fmt(x4)} | percentil por etapas, recalculable | {'DEMOSTRADO' if x4[0] is not None else 'PENDIENTE'} |")
    E.append(f"| M5 | `X5_confidence_psi` PSI vs referencia | 8 si el caso controlado muestra el cambio (PSI C1 < 0.1 ≤ PSI S2), si no 5 | C1: {fmt(psi_c1)}; S2: {fmt(psi_s2)} | comparación con la referencia + caso controlado | {'DEMOSTRADO nivel 8' if psi_ok else ('DEMOSTRADO nivel 5 (sin caso controlado)' if psi_c1[0] is not None else 'PENDIENTE')} |")
    E.append(f"| M6 | `X6_invalid_input_rate` entradas inválidas | 5 | {fmt(x6)} | proporción, verificada en S3 | {'DEMOSTRADO' if (x6[0] or 0) > 0 else 'PENDIENTE'} |")
    E += ["", "Ninguna de estas métricas es la métrica base de su grupo (ver `docs/inventario-metricas.md`).", ""]

    shots = EVID / "portal"
    def shot(n: str) -> bool:
        return (shots / n).is_file()
    E += ["## Funcionalidades adicionales (F)", "", "| ID | Funcionalidad | Nivel | Evidencia | Estado |", "| --- | --- | --- | --- | --- |"]
    for fid, title, pts, tests, img in (
        ("F1", "Visualización del stream en vivo con la predicción (`/live`, `/api/live`)", 5, "tests/test_portal.py", "live.png"),
        ("F2", "Dashboard con gráficas históricas por run (`/`, `/api/series`): confianza con umbrales, zonas, histograma vs referencia, latencia; selección de run, estado vacío y de error", 10, "tests/test_portal.py", "dashboard.png"),
        ("F3", "Filtros avanzados de eventos/alertas (11 criterios validados) y exportación CSV/JSON del resultado filtrado, con errores 400 y estado vacío", 10, "tests/test_portal.py", "events-filtered.png"),
        ("F4", "Revisión manual de capturas (galería, veredicto y nota persistidos, filtro por revisión, redirección segura)", 10, "tests/test_portal.py", "gallery-review.png"),
    ):
        has = shot(img)
        E.append(f"| {fid} | {title} | {pts} | `{tests}`, `evidence/portal/{img}` | {'DEMOSTRADO' if has else 'PENDIENTE — falta la captura evidence/portal/' + img} |")
    E += ["", "## Totales", "",
          "El total sumado se calcula con los elementos en estado DEMOSTRADO; no hay tope ni normalización. "
          "Los puntos de la base (R1–R7) se evalúan por separado.", ""]
    return "\n".join(L), "\n".join(E)


def write(data_dir: str | Path = "data") -> None:
    idx, extras = build(data_dir)
    EVID.mkdir(exist_ok=True)
    (EVID / "INDEX.md").write_text(idx, encoding="utf-8")
    (EVID / "EXTRAS.md").write_text(extras, encoding="utf-8")
