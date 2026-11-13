# Evidencia · S3 · run `S3-20261113-104951`

## Identidad de la ejecución

- Escenario: `S3`  · inicio 2026-11-13T16:49:51.680Z · fin 2026-11-13T16:50:07.391Z
- Commit del código: `d5f99ba506822917503c6ae9edea3751da69bcbc` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `b4862bc36174ae3c` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (sequence)
- Modelo: `mobilenetv2-12` / `mobilenetv2-12` sha256 `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5`
- Notas: S3 entradas invalidas: 30 imagenes reales de C1, 3 truncadas a 1/3 (0005, 0012, 0020)

## Resultados

- Eventos: 30 · por zona/estado: {"accepted": 27, "invalid_input": 3}
- Alertas: 0

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 27 inferencias ok; sha256 del run C0C3F76D93FA… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 27/27 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 3/3 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 0 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | insufficient_evidence=4, ok=9 |
| S3.a | Se registraron entradas inválidas sin detener el pipeline | PASA | invalid=3, ok=27 |
| S3.b | Las entradas inválidas no tienen puntuación ni zona (estado aparte) | PASA |  |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Evento `E-S3-20261113-104951-000001` · computer keyboard, keypad 0.8707319916542623 · zona accepted · captura `captures/S3-20261113-104951/E-S3-20261113-104951-000001.jpg`

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para S3-20261113-104951

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95              85.171930       85.171930      27  OK
G2_processing_fps                 1.753821        1.753821      27  OK
G3_process_rss_mb               126.164082      126.164082       9  OK
G4_low_conf_share                 0.000000        0.000000      27  OK
G5_trace_coverage                 1.000000        1.000000      30  OK
G6_version_match_share            1.000000        1.000000      30  OK
G7_active_alerts                  0.000000        0.000000       0  OK
X1_capture_fps                    1.752240        1.752240      27  OK
X2_dropped_share                  0.000000        0.000000      27  OK
X3_process_cpu_pct              464.411111      464.411111       9  OK
X4_e2e_ms_p95                   195.328641      195.328641      27  OK
X5_confidence_psi                     None            None      27  OK
X6_invalid_input_rate             0.100000        0.100000      30  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/S3-20261113-104951/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/S3/inputs`
