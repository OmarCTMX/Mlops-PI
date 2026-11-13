"""CLI: python -m cvmon <comando>"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import db
from .config import ROOT, apply_overrides, load_config, resolve


def _cfg(args) -> dict:
    cfg = load_config(args.config)
    return apply_overrides(cfg, getattr(args, "set", None) or [])


def cmd_run(args) -> int:
    from .pipeline import Pipeline

    cfg = _cfg(args)
    p = Pipeline(cfg, args.data_dir, args.scenario, duration_s=args.duration, max_events=args.max_events,
                 record_inputs=args.record_inputs, notes=args.notes)
    p.run()
    return 0


def cmd_check_source(args) -> int:
    from .model import Classifier
    from .policy import classify_zone
    from .source import make_source

    cfg = _cfg(args)
    src = make_source(cfg["source"])
    src.open()
    fr = src.read()
    src.close()
    clf = Classifier(cfg["model"])
    pred = clf.predict(fr.image)
    zone = classify_zone(pred["confidence"], cfg["thresholds"]["lower"], cfg["thresholds"]["upper"])
    print(f"Frame {fr.image.shape[1]}x{fr.image.shape[0]} de '{cfg['source']['id']}'")
    print(f"Predicción: {pred['label']}  confianza={pred['confidence']:.3f}  zona={zone}  "
          f"inferencia={pred['inference_ms']:.1f} ms")
    for t in pred["topk"]:
        print(f"   {t['score']:.3f}  {t['label']}")
    if args.save:
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save).write_bytes(fr.raw_jpeg or b"")
    return 0


def cmd_portal(args) -> int:
    import uvicorn

    from .portal.app import create_app

    app = create_app(args.data_dir, args.config)
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_export(args) -> int:
    from .export import export_jsonl

    conn = db.open_db(Path(args.data_dir) / "cvmon.db")
    counts = export_jsonl(conn, args.out, args.runs or None)
    ref = resolve("config/reference.json")
    if ref.is_file():
        (Path(args.out) / "reference.json").write_text(ref.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(counts, indent=2))
    return 0


def cmd_recalc(args) -> int:
    from .recalc import format_report, recalc_run

    rows = recalc_run(args.export, args.data_dir, args.run)
    text = format_report(args.run, rows)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    return 0 if all(r["match"] for r in rows) else 1


def cmd_reference(args) -> int:
    from .reference import build_reference

    conn = db.open_db(Path(args.data_dir) / "cvmon.db")
    ref = build_reference(conn, args.runs, args.out)
    print(f"Referencia escrita en {args.out}: n={ref['n']} media={ref['mean']:.4f} "
          f"p05={ref['percentiles']['p05']:.3f} p25={ref['percentiles']['p25']:.3f}")
    return 0


def cmd_thresholds(args) -> int:
    from .reference import justification_markdown, suggest_thresholds

    cfg = load_config(args.config)
    ref = json.loads(resolve(cfg["reference"]["path"]).read_text(encoding="utf-8"))
    conn = db.open_db(Path(args.data_dir) / "cvmon.db")
    lo, up = suggest_thresholds(ref)
    print(f"Sugerencia por regla (P05/P25): inferior={lo:.2f} superior={up:.2f}")
    md = justification_markdown(ref, cfg["thresholds"]["lower"], cfg["thresholds"]["upper"], conn)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"Justificación escrita en {args.out}")
    return 0


def cmd_finalize(args) -> int:
    from .evidence import finalize

    cfg = load_config(args.config)
    res = finalize(args.data_dir, args.run, args.out, args.kind, resolve(cfg["model"]["path"]), args.inputs)
    bad = [c for c in res["checks"] if not c["passed"]]
    for c in res["checks"]:
        print(f"[{'PASA ' if c['passed'] else 'FALLA'}] {c['id']:<6} {c['description']} :: {c['detail']}")
    print(f"\nEvidencia escrita en {args.out}")
    return 1 if bad else 0


def cmd_index(args) -> int:
    from .index import write

    write(args.data_dir)
    print("Escritos evidence/INDEX.md y evidence/EXTRAS.md")
    return 0


def cmd_run_id(args) -> int:
    conn = db.open_db(Path(args.data_dir) / "cvmon.db")
    r = conn.execute("SELECT run_id FROM runs WHERE scenario=? ORDER BY started_epoch DESC LIMIT 1",
                     (args.scenario,)).fetchone()
    if not r:
        print(f"No hay runs del escenario {args.scenario}", file=sys.stderr)
        return 1
    print(r[0])
    return 0


def cmd_replay_check(args) -> int:
    from .evidence import replay_check

    res = replay_check(args.data_dir, args.orig, args.replay)
    print(json.dumps(res, indent=2))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    return 0 if res["identical"] else 1


def cmd_metrics(args) -> int:
    conn = db.open_db(Path(args.data_dir) / "cvmon.db")
    run_id = args.run or conn.execute("SELECT run_id FROM runs ORDER BY started_epoch DESC LIMIT 1").fetchone()[0]
    rows = conn.execute(
        "SELECT m.* FROM metric_samples m JOIN (SELECT metric_id, MAX(ts) t FROM metric_samples WHERE run_id=? "
        "GROUP BY metric_id) x ON m.metric_id=x.metric_id AND m.ts=x.t WHERE m.run_id=? ORDER BY m.metric_id",
        (run_id, run_id)).fetchall()
    print(f"Métricas de {run_id}")
    for r in rows:
        v = "None" if r["value"] is None else f"{r['value']:.4f}"
        print(f"  {r['metric_id']:<26}{r['grp']:<4}{v:>14}  n={r['n']}  {r['detail']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cvmon", description="Centro de monitoreo de computer vision")
    ap.add_argument("--config", default="config/config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--data-dir", default="data")
        p.add_argument("--set", action="append", metavar="clave=valor", help="override de configuración")

    p = sub.add_parser("run", help="ejecutar el pipeline"); common(p)
    p.add_argument("--scenario", required=True, help="etiqueta del run: REF, C1, C2, S1...")
    p.add_argument("--duration", type=float, default=None, help="segundos")
    p.add_argument("--max-events", type=int, default=None)
    p.add_argument("--record-inputs", default=None, help="carpeta donde guardar las imágenes de entrada")
    p.add_argument("--notes", default=None)
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("check-source", help="probar fuente + modelo con un frame"); common(p)
    p.add_argument("--save", default=None)
    p.set_defaults(fn=cmd_check_source)

    p = sub.add_parser("portal", help="levantar el portal web"); common(p)
    p.add_argument("--host", default="127.0.0.1"); p.add_argument("--port", type=int, default=8000)
    p.set_defaults(fn=cmd_portal)

    p = sub.add_parser("export", help="exportar tablas a JSONL"); common(p)
    p.add_argument("--out", required=True); p.add_argument("--runs", nargs="*")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("recalc", help="recalcular métricas de forma independiente"); common(p)
    p.add_argument("--export", required=True); p.add_argument("--run", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_recalc)

    p = sub.add_parser("reference", help="construir la referencia de confianza"); common(p)
    p.add_argument("--runs", nargs="+", required=True)
    p.add_argument("--out", default="config/reference.json")
    p.set_defaults(fn=cmd_reference)

    p = sub.add_parser("thresholds", help="justificar umbrales con la referencia"); common(p)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_thresholds)

    p = sub.add_parser("finalize", help="exportar, recalcular y verificar un escenario"); common(p)
    p.add_argument("--run", required=True); p.add_argument("--out", required=True)
    p.add_argument("--kind", default="generic", choices=["generic", "C1", "C2", "S1", "S2", "S3", "S4"])
    p.add_argument("--inputs", default=None)
    p.set_defaults(fn=cmd_finalize)

    p = sub.add_parser("index", help="generar evidence/INDEX.md y evidence/EXTRAS.md"); common(p)
    p.set_defaults(fn=cmd_index)

    p = sub.add_parser("run-id", help="imprimir el último run_id de un escenario"); common(p)
    p.add_argument("--scenario", required=True)
    p.set_defaults(fn=cmd_run_id)

    p = sub.add_parser("replay-check", help="comparar un run con su reproducción desde las entradas"); common(p)
    p.add_argument("--orig", required=True); p.add_argument("--replay", required=True)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_replay_check)

    p = sub.add_parser("metrics", help="mostrar las métricas de un run"); common(p)
    p.add_argument("--run", default=None)
    p.set_defaults(fn=cmd_metrics)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
