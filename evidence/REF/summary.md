# Evidencia · REF · run `REF-20261113-094929`

## Identidad de la ejecución

- Escenario: `REF`  · inicio 2026-11-13T15:49:29.989Z · fin 2026-11-13T15:52:30.200Z
- Commit del código: `0fb5e9047f0115a659864a111554277fec198a90` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `9f318c1693e4994e` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (ipwebcam)
- Modelo: `mobilenetv2-12` / `mobilenetv2-12` sha256 `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5`
- Notas: Referencia: teclado de laptop, vista superior, celular fijo, luz de interior

## Resultados

- Eventos: 167 · por zona/estado: {"accepted": 138, "doubt": 28, "low": 1}
- Alertas: 0

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 167 inferencias ok; sha256 del run C0C3F76D93FA… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 167/167 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 43/43 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 0 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | insufficient_evidence=22, ok=68 |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Evento `E-REF-20261113-094929-000001` · computer keyboard, keypad 0.8320215415253537 · zona accepted · captura `captures/REF-20261113-094929/E-REF-20261113-094929-000001.jpg`

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para REF-20261113-094929

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95             159.024150      159.024150     167  OK
G2_processing_fps                 0.928728        0.928728     167  OK
G3_process_rss_mb               129.459588      129.459588      87  OK
G4_low_conf_share                 0.005988        0.005988     167  OK
G5_trace_coverage                 1.000000        1.000000     167  OK
G6_version_match_share            1.000000        1.000000     167  OK
G7_active_alerts                  0.000000        0.000000       0  OK
X1_capture_fps                    4.555396        4.555396     820  OK
X2_dropped_share                  0.795122        0.795122     820  OK
X3_process_cpu_pct              220.733333      220.733333      87  OK
X4_e2e_ms_p95                   420.718360      420.718360     167  OK
X5_confidence_psi                     None            None     167  OK
X6_invalid_input_rate             0.000000        0.000000     167  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/REF-20261113-094929/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/REF/inputs`
