# Inventario de métricas G1–G7 (R2)

**Cada uno de los siete grupos tiene una métrica base implementada en código** (`cvmon/metrics.py`), medida en cada run
y recalculable (`cvmon/recalc.py`); no hay grupos solo documentados.

| Grupo | Aplica | Métrica base (implementada) |
| --- | --- | --- |
| G1 Salud y rendimiento | Sí | `G1_inference_ms_p95` — tiempo de inferencia p50/p95 |
| G2 Captura y stream | Sí | `G2_processing_fps` — FPS de procesamiento |
| G3 Recursos | Sí | `G3_process_rss_mb` — RAM del proceso |
| G4 Predicciones | Sí | `G4_low_conf_share` — proporción de baja confianza |
| G5 Datos y trazabilidad | Sí | `G5_trace_coverage` — cobertura de trazabilidad |
| G6 Fuentes y versiones | Sí | `G6_version_match_share` — versión esperada frente a reportada |
| G7 Alertas | Sí | `G7_active_alerts` — alertas activas |

Exclusiones: **ninguna**. Los **siete grupos aplican** (G = 7): el sistema infiere sobre un stream (G1, G2), corre en un
proceso con CPU/RAM medibles (G3), produce puntuaciones sin etiquetas (G4), persiste eventos e imágenes (G5), tiene
una fuente y una versión de modelo (G6) y genera alertas (G7). Una métrica **no** se usa en dos grupos.

Fórmula de la rúbrica: `R2 = 25 × Σ(M1..M5 de los 7 grupos) / (5 × 7)`.

Convenciones comunes (M1/M3):

- **Población**: observaciones del run indicado hasta el instante de referencia `T` (fin del run o instante de cada
  muestra periódica de `metric_samples`).
- **Cero observaciones** ⇒ `value = NULL` y `detail.reason = "sin_observaciones"`. Nunca se informa 0 ni 1 inventados.
- **Percentiles**: interpolación lineal (`pos = (n-1)·q`), idéntica a `numpy.percentile` por defecto.
- **Adquisición (M2)**: todas las observaciones las produce `cvmon/pipeline.py` en SQLite (`data/cvmon.db`).
- **Verificación (M5)**: `python -m cvmon export …` + `python -m cvmon recalc …` recalculan **sin reutilizar**
  `cvmon/metrics.py` (usa numpy sobre los JSONL). Resultado guardado en `evidence/<escenario>/recalc.txt`.

## Métricas base

| Grupo | `metric_id` | M1 Definición (qué mide, unidad, fórmula, población) | M2 Adquisición | M3 Cálculo / cero datos | M4 Trazabilidad | M5 Verificación |
| --- | --- | --- | --- | --- | --- | --- |
| G1 Salud/rendimiento | `G1_inference_ms_p95` | Tiempo de `session.run` del modelo (ms), p95 (y p50 en `detail`), sobre eventos `status=ok`. Excluye captura, preprocesamiento y envío. | `time.perf_counter` alrededor de `session.run` → `events.inference_ms` | Percentil lineal; sin eventos ok → NULL | Cada valor sale de `events.inference_ms`; `/events?run=…` lista las filas | `recalc` con `numpy.percentile(95)` |
| G2 Stream | `G2_processing_fps` | Frames inferidos por segundo en régimen: `(n−1)/(t_último − t_primero)` de `processed_epoch`, eventos `ok`. Excluye el arranque. | `events.processed_epoch` | `n < 2` o span 0 → NULL (`reason=menos_de_2_frames`) | Filas de `events` | `recalc` desde `events.jsonl` |
| G3 Recursos | `G3_process_rss_mb` | Media de la memoria residente (RSS, MB) del **proceso** de inferencia, muestreada cada `resources.sample_interval_s` (2 s). | `psutil.Process().memory_info().rss` → `resource_samples` | Sin muestras → NULL; `max/min` en `detail` | Filas de `resource_samples` | `recalc` (media numpy) |
| G4 Predicciones | `G4_low_conf_share` | Proporción de eventos en zona `low` (s < umbral inferior) entre eventos con puntuación (`status=ok`). No es tasa de error. | `events.zone` | Sin puntuados → NULL | `/events?zone=low` | `recalc` (conteo) |
| G5 Datos/trazabilidad | `G5_trace_coverage` | Eventos con todos los campos obligatorios, `config_hash` resoluble en `config_snapshots`, y, si tienen `capture_path`, el archivo existente en disco; entre **todos** los eventos del run. | Verificación sobre `events` + sistema de archivos | Sin eventos → NULL | `detail.complete`; eventos incompletos se identifican por `event_id` | `recalc` repite las comprobaciones, incluida la existencia de archivos (`--data-dir`) |
| G6 Fuentes/versiones | `G6_version_match_share` | Proporción de eventos cuyo `model_version` reportado coincide con `model.expected_version` de **su** configuración; `detail` lista versiones reportadas. | `events.model_version` + `config_snapshots` | Sin eventos → NULL | `/events?model_version=…` | `recalc` desde JSONL |
| G7 Alertas | `G7_active_alerts` | Alertas del run con `fired_epoch ≤ T` y no resueltas en `T`. | tabla `alerts` | 0 alertas → valor 0 (cero observaciones de alertas es un dato válido: no hubo alertas) | `/alerts?status=active` | `recalc` desde `alerts.jsonl` |

## Métricas adicionales (no cuentan para R2; ver `evidence/EXTRAS.md`)

| `metric_id` | Grupo | Descripción |
| --- | --- | --- |
| `X1_capture_fps` | G2 | FPS de captura `(n−1)/span` de `stream_obs.kind=captured` (distinto del FPS de inferencia: mide otra etapa) |
| `X2_dropped_share` | G2 | Frames descartados por la aplicación / capturados, separados por motivo (`sampling`, `saturation`) |
| `X3_process_cpu_pct` | G3 | Media del % de CPU del proceso (psutil; puede superar 100 con hilos) |
| `X4_e2e_ms_p95` | G2 | p95 de captura→resultado, con desglose de cola, preprocesamiento e inferencia |
| `X5_confidence_psi` | G4 | PSI de la distribución de confianza frente a la referencia (10 bins, ε=1e‑4, ≥30 muestras) |
| `X6_invalid_input_rate` | G5 | Entradas inválidas / eventos |

## Dónde verlas

- Portal: `/metrics?run=<run_id>` (valor, n, definición y detalle).
- CLI: `python -m cvmon metrics --run <run_id>`.
- Tabla `metric_samples` (una captura cada `metrics.snapshot_interval_s` y una final al cerrar el run).
