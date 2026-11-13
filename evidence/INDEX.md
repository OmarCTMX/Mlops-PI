# Índice de evidencias (criterio → archivo/ID)

Generado con `python -m cvmon index`. Autoría individual: ver `README.md`.

## Revisiones Git

- Commit actual del repositorio al generar este índice: `0771e330976ade4c33b5091aff0d05bbaa0413a9`.
- Cada `run` guarda en `runs.git_commit` el commit del **código** con el que se ejecutó (ver tabla de runs).
- Las evidencias (`data/`, `evidence/`) se incorporan en un commit **posterior** al código probado;
  el código no cambia entre ambos (el campo `git_dirty` indica si el árbol de código tenía cambios al ejecutar).

## Runs de evidencia

| Escenario | run_id | Commit del código | Config | Modelo | Verificaciones |
| --- | --- | --- | --- | --- | --- |
| REF | `REF-20261113-094929` | `0fb5e9047f` (sucio) | `9f318c1693e4994e` | mobilenetv2-12 | PASA |
| C1 | `C1-20261113-095839` | `d5f99ba506` (sucio) | `14f760df47efe344` | mobilenetv2-12 | PASA |
| C1 | `C1-20261113-100136` | `d5f99ba506` (sucio) | `14f760df47efe344` | mobilenetv2-12 | PASA |
| C1 | `C1-20261113-103945` | `d5f99ba506` (sucio) | `14f760df47efe344` | mobilenetv2-12 | PASA |
| C2 | `C2-20261113-104622` | `d5f99ba506` (sucio) | `14f760df47efe344` | mobilenetv2-12 | PASA |
| C1-REPLAY | `C1-REPLAY-20261113-104923` | `d5f99ba506` (sucio) | `e4a55a47ccc9a24d` | mobilenetv2-12 | - |
| C2-REPLAY | `C2-REPLAY-20261113-104932` | `d5f99ba506` (sucio) | `68c8c5e843de0c91` | mobilenetv2-12 | - |
| S3 | `S3-20261113-104951` | `d5f99ba506` (sucio) | `b4862bc36174ae3c` | mobilenetv2-12 | PASA |
| S4 | `S4-20261113-105503` | `9b6c31e3e6` (sucio) | `ff7073511cfde98f` | mobilenetv2-7 | PASA |
| S2 | `S2-20261113-110107` | `0771e33097` (sucio) | `14f760df47efe344` | mobilenetv2-12 | PASA |
| S1 | `S1-20261113-110644` | `0771e33097` (sucio) | `14f760df47efe344` | mobilenetv2-12 | PASA |
| LIVE | `LIVE-20261113-110958` | `0771e33097` (sucio) | `14f760df47efe344` | mobilenetv2-12 | - |

## Rúbrica → evidencia

| Criterio | Dónde está | Evidencia verificable |
| --- | --- | --- |
| R1.1 fuente y muestreo | `config/config.yaml` (source, sampling), `cvmon/source.py`, `cvmon/pipeline.py`, `docs/politica-confianza-y-alertas.md` | `evidence/C1/exports/stream_obs.jsonl` (captured/dropped por motivo), métrica `X1_capture_fps`, `X2_dropped_share` |
| R1.2 inferencia real | `cvmon/model.py` (ONNX Runtime) | verificaciones V1 y V2 en `evidence/*/verification.json` (confianza = top‑1 del modelo; sha256 del modelo); `replay_check.json` (mismas entradas ⇒ mismos scores) |
| R1.3 identidad del modelo | `models/MODEL_CARD.md`, `runs.model_identity_json` | portal `/runs/<run_id>`; `evidence/*/exports/runs.jsonl` |
| R2 métricas G1–G7 | `docs/inventario-metricas.md`, `cvmon/metrics.py`, `cvmon/recalc.py` | `evidence/*/recalc.txt`; portal `/metrics` |
| R3.1 umbrales y justificación | `config/config.yaml` (thresholds), `cvmon/reference.py` | `evidence/REF/threshold_justification.md` |
| R3.2 tres zonas | `cvmon/policy.py`, `tests/test_policy_config.py` | `events.zone` en `evidence/*/exports/events.jsonl`; `/events?zone=…` |
| R3.3 referencia, ventanas, cambio sostenido | `config/reference.json`, `config/config.yaml` (R-SHIFT), `docs/politica-confianza-y-alertas.md` | `rule_evaluations.jsonl` (incluye `insufficient_evidence`) |
| R4.1 eventos | `cvmon/db.py` (tabla events), `cvmon/pipeline.py` | `evidence/*/exports/events.jsonl` |
| R4.2 persistencia y consulta en portal | `cvmon/portal/app.py`, `data/cvmon.db` | `/events`, `/events/<id>`; `tests/test_portal.py`; capturas de pantalla en `evidence/portal/` |
| R4.3 imágenes sin expiración | `config/config.yaml` (capture), `data/captures/<run_id>/` | verificación V3 (cada captura existe); no hay código de borrado/TTL |
| R5.1 reglas | `config/config.yaml` (alerts.rules), `cvmon/alerts.py`, `docs/politica-confianza-y-alertas.md` | `tests/test_alerts.py` |
| R5.2 alertas desde observaciones reales | `cvmon/alerts.py`, tablas `alerts`/`alert_events` | verificación V4; sección “Cadena de una muestra” de `evidence/*/summary.md` |
| R5.3 alertas en el portal | `/alerts`, `/alerts/<id>` | capturas en `evidence/portal/` |
| R6.1 C1 operación normal | `scripts/scenario.ps1`, `docs/escenarios.md` | `evidence/C1/` (summary.md, verification.json, exports, inputs, replay_check.json) |
| R6.2 C2 baja confianza | `scripts/scenario.ps1`, `docs/escenarios.md` | `evidence/C2/` (ídem) |
| R7.1 instalación y comandos | `README.md`, `requirements.txt`, `scripts/` | — |
| R7.2 evidencias ligadas al commit | este índice, tabla de runs | `recalc.txt`, `replay_check.json` |
| R7.3 autoría y procedencia | `README.md`, `models/MODEL_CARD.md` | — |

## Estado de C1/C2

- C1: **PASA** — todas las verificaciones pasan
- C2: **PASA** — todas las verificaciones pasan

Inventario de extras reclamados: `evidence/EXTRAS.md`.
