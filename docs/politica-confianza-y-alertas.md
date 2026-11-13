# Política de confianza, captura y alertas (R3, R4.3, R5)

Todos los valores viven en `config/config.yaml`. El hash de la configuración (`config_hash`) se guarda en cada
evento y en cada alerta; la configuración completa se conserva en `config_snapshots`.

## Muestreo del stream (R1.1)

- La fuente se lee a `source.capture_fps` frames/s (ritmo de captura/reproducción).
- Política de muestreo: se **infiere un frame cada `sampling.sample_interval_s`** segundos (por defecto 1 s ⇒ ~1 inferencia/s).
  El resto se descarta con motivo `sampling` (`stream_obs.kind=dropped`).
- Cola de inferencia de `sampling.queue_size` elementos: si está llena, el frame se descarta con motivo `saturation`
  (en fuentes finitas —video o secuencia— se aplica contrapresión y no se pierden frames).
- `sample_interval_s: 0` infiere todos los frames (se usa solo para reproducir entradas guardadas).

- **Frames consecutivos no son observaciones independientes.** Un stream a 5 fps produce frames casi idénticos;
  por eso se muestrea 1 inferencia/s, y las ventanas de las reglas (10–15 inferencias ≈ 10–15 s) se interpretan como
  “persistencia durante un intervalo”, no como 10–15 muestras independientes. Las proporciones informan sobre el
  intervalo observado, sin pretender inferencia estadística.
- Unidad de análisis: **una imagen (frame) inferida** = un evento. En clasificación no hay detecciones múltiples.

## Dos umbrales y tres zonas (R3.1, R3.2)

Sea `s` la confianza top‑1 (softmax). Con `0 ≤ inferior < superior ≤ 1` (validado al cargar la configuración):

| Zona | Condición | Significado |
| --- | --- | --- |
| `accepted` | `s ≥ superior` | aceptada **por política** (no afirma que el modelo acertó) |
| `doubt` | `inferior ≤ s < superior` | duda |
| `low` | `s < inferior` | baja confianza |

Estados **aparte** (no son zonas, `zone = NULL`, `confidence = NULL`): `inference_error` (fallo técnico del modelo) y
`invalid_input` (imagen no decodificable). Se cuentan por separado de baja confianza.

Los valores 0.60/0.80 de la rúbrica son un ejemplo; aquí los umbrales se **derivan de la referencia**
(`evidence/REF/threshold_justification.md`): superior = P25 y inferior = P05 de la confianza observada en la escena
de referencia, redondeados hacia abajo a múltiplos de 0.05. Se congelan **antes** de ejecutar C1 y C2.

Las pruebas de borde de la política están en `tests/test_policy_config.py`.

## Referencia, ventanas y cambio sostenido (R3.3)

- **Referencia**: `config/reference.json`, construida con inferencias reales del escenario `REF`
  (`python -m cvmon reference`). Guarda n, media, desviación, percentiles, histograma de 10 bins, identidad del
  modelo y commits. Solo es válida para el mismo modelo/preprocesamiento/configuración; si cambian, se separan series.
- **Mínimo de observaciones**: `reference.min_observations` (30) y `min_samples` por regla.
- **Evidencia insuficiente ≠ normalidad**: si no hay `min_samples` observaciones (o referencia), la evaluación se
  registra como `insufficient_evidence` en `rule_evaluations`; no cuenta como “ok” ni resuelve alertas activas.
- **Regla de cambio sostenido** `R-SHIFT`: media de las últimas `window_events` (15) confianzas < media de referencia −
  `drop_delta` (0.15), **durante `sustain_events` (5) evaluaciones consecutivas** con ventana completa.

## Política de captura de imágenes (R4.3)

- Se conserva la imagen de **todo evento en zona `low` o `doubt`** y **1 de cada `normal_sample_every_n` (10)
  aceptados** (muestra normal, empezando por el primero). No se guardan todos los frames.
- El archivo es el JPEG original que entregó la fuente (sin recomprimir): `data/captures/<run_id>/<event_id>.jpg`;
  `events.capture_path` apunta a él y `events.capture_reason` dice por qué se guardó.
- **Sin expiración automática**: el código no contiene ningún proceso de borrado, TTL ni rotación.

## Reglas de alerta (R5.1)

Cada evaluación registra `ok | pending | firing | insufficient_evidence`. Mientras una alerta de una regla esté
activa no se genera otra igual (sin alertas repetidas); se **resuelve** con histéresis cuando la condición se aclara.

| ID | Tipo | Condición | Persistencia / ventana | Datos insuficientes | Severidad | Acción sugerida |
| --- | --- | --- | --- | --- | --- | --- |
| `R-LOWCONF` | `low_confidence_share` | proporción de zona `low` ≥ 0.50 | últimas 10 inferencias con puntuación | < 6 muestras → `insufficient_evidence` | high | Revisar encuadre, iluminación y enfoque; inspeccionar capturas |
| `R-SHIFT` | `confidence_shift` | media reciente < media de referencia − 0.15 | ventana 15, 5 evaluaciones consecutivas | < 10 muestras o referencia ausente/corta → `insufficient_evidence` | medium | Comparar con la referencia; verificar escena, versión y preprocesamiento |
| `R-STALE` | `stream_stale` | sin frames válidos > 10 s | evaluada cada segundo | antes de 10 s desde el inicio sin frames → `insufficient_evidence` | critical | Verificar app/cámara, red y URL; reiniciar captura |
| `R-INFERR` | `inference_error_rate` | fallos / intentos > 0.30 | últimos 10 intentos | < 5 intentos → `insufficient_evidence` | high | Revisar el log de errores y la validez de las imágenes |
| `R-VERSION` | `version_mismatch` | versión reportada ≠ `model.expected_version` en todos los eventos de la ventana | últimos 5 eventos | < 5 eventos → `insufficient_evidence` | medium | Confirmar el artefacto desplegado o actualizar la versión esperada tras validarla |

## Correspondencia con el contrato de ejemplo de la guía (R4.1)

| Campo de la guía | Campo en este sistema (`events` / `alerts`) |
| --- | --- |
| `event_id` | `events.event_id` (`E-<run_id>-<seq>`) |
| `run_id` | `events.run_id` (tabla `runs`: commit, configuración, modelo) |
| `frame_id` | `events.frame_id` (`F-<run_id>-<n>`, contador de frames recibidos; también en `stream_obs.detail`) |
| `timestamp` | `events.captured_at` (UTC ISO‑8601) y `captured_epoch` |
| `source_id` | `events.source_id` (+ `source_ref`: archivo o recurso de origen) |
| `task` | `events.task` (`classification`) |
| `model_ref` | `events.model_id` + `events.model_version` (sha256 e identidad completa en `runs`) |
| `status` | `events.status` (`ok` · `inference_error` · `invalid_input`) |
| `prediction.class_id` / `prediction.score` | `events.pred_class_id`, `pred_label` / `events.confidence` (+ `topk_json`) |
| `confidence_zone` | `events.zone` (`accepted` · `doubt` · `low` · NULL sin puntuación) |
| `config_ref` | `events.config_hash` → `config_snapshots.config_json` (+ `threshold_lower/upper` copiados en el evento) |
| `image_ref` | `events.capture_path` (relativo a `data/`) + `capture_reason` |
| alerta `alert_id`, `rule_id`, `timestamp`, `severity` | `alerts.alert_id`, `rule_id` (+ `rule_json`), `fired_at`, `severity` |
| alerta `event_ids` | tabla `alert_events` (alerta ↔ eventos de la ventana) |
| alerta `config_ref`, `reason`, `suggested_action` | `alerts.config_hash`, `reason`, `suggested_action` (+ `observation_json`, ventana, estado/resolución) |

## Trazabilidad de una alerta (R5.2)

`alerts` guarda: regla completa (`rule_json`), `config_hash`, ventana (`window_start/end_epoch`), motivo con los
valores observados, `observation_json`, severidad y acción. `alert_events` enlaza los **eventos** de la ventana.
Se generan únicamente desde el pipeline (`cvmon/alerts.py`), a partir de eventos u observaciones reales; las pruebas
sintéticas de `tests/test_alerts.py` verifican la lógica de las reglas y **no** sustituyen a C1/C2.
