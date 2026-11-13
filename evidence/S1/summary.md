# Evidencia · S1 · run `S1-20261113-110644`

## Identidad de la ejecución

- Escenario: `S1`  · inicio 2026-11-13T17:06:44.431Z · fin 2026-11-13T17:08:44.607Z
- Commit del código: `0771e330976ade4c33b5091aff0d05bbaa0413a9` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `14f760df47efe344` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (ipwebcam)
- Modelo: `mobilenetv2-12` / `mobilenetv2-12` sha256 `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5`
- Notas: S1 interrupcion: teclado; a los ~30 s se detiene el servidor de IP Webcam y a los ~60 s se reinicia

## Resultados

- Eventos: 93 · por zona/estado: {"accepted": 91, "invalid_input": 2}
- Alertas: 1

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |
| `A-S1-20261113-110644-0001` | R-STALE | critical | resolved | Sin frames válidos durante 10.6s desde el último frame válido (máximo permitido 10.0s) |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 91 inferencias ok; sha256 del run C0C3F76D93FA… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 91/91 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 10/10 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 1 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | firing=2, insufficient_evidence=5, ok=49 |
| S1.a | Se detectó la interrupción (alerta R-STALE) | PASA | 1 alertas |
| S1.b | Hubo fallos de lectura e intentos de reconexión | PASA | {'captured': 450, 'dropped': 359, 'invalid_frame': 2, 'read_fail': 1, 'reconnect_attempt': 5, 'reconnect_ok': 1} |
| S1.c | La fuente se recuperó (reconnect_ok) y la alerta se resolvió | PASA | reconnect_ok=1 |
| S1.d | Verificación posterior: hay inferencias reales tras la recuperación | PASA | 55 inferencias posteriores |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Alerta `A-S1-20261113-110644-0001` (regla R-STALE, config `14f760df47efe344`):
- evento `E-S1-20261113-110644-000036` · None None · zona None · captura `-` · existe: None

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para S1-20261113-110644

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95               7.573800        7.573800      91  OK
G2_processing_fps                 0.755000        0.755000      91  OK
G3_process_rss_mb               127.093812      127.093812      59  OK
G4_low_conf_share                 0.000000        0.000000      91  OK
G5_trace_coverage                 1.000000        1.000000      93  OK
G6_version_match_share            1.000000        1.000000      93  OK
G7_active_alerts                  0.000000        0.000000       1  OK
X1_capture_fps                    3.753810        3.753810     450  OK
X2_dropped_share                  0.797778        0.797778     450  OK
X3_process_cpu_pct              245.703390      245.703390      59  OK
X4_e2e_ms_p95                   196.532249      196.532249      91  OK
X5_confidence_psi                15.502461       15.502461      91  OK
X6_invalid_input_rate             0.021505        0.021505      93  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/S1-20261113-110644/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/S1/inputs`
