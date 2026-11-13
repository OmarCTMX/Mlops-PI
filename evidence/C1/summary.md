# Evidencia · C1 · run `C1-20261113-103945`

## Identidad de la ejecución

- Escenario: `C1`  · inicio 2026-11-13T16:39:45.080Z · fin 2026-11-13T16:41:45.351Z
- Commit del código: `d5f99ba506822917503c6ae9edea3751da69bcbc` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `14f760df47efe344` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (ipwebcam)
- Modelo: `mobilenetv2-12` / `mobilenetv2-12` sha256 `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5`
- Notas: C1 operacion normal (tercer intento): teclado de laptop como en REF, celular fijo sin tocar

## Resultados

- Eventos: 110 · por zona/estado: {"accepted": 110}
- Alertas: 0

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 110 inferencias ok; sha256 del run C0C3F76D93FA… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 110/110 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 11/11 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 0 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | insufficient_evidence=5, ok=59 |
| C1.a | Operación normal: hay inferencias suficientes (>= 20) y zona aceptada observada | PASA | ok=110 zonas={'accepted': 110, 'doubt': 0, 'low': 0} |
| C1.b | Operación normal: la baja confianza no domina (< 20 % de las inferencias) | PASA | baja=0.00 |
| C1.c | Sin alerta de baja confianza durante la operación normal | PASA | 0 alertas R-LOWCONF |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Evento `E-C1-20261113-103945-000001` · computer keyboard, keypad 0.8707319916542623 · zona accepted · captura `captures/C1-20261113-103945/E-C1-20261113-103945-000001.jpg`

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para C1-20261113-103945

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95             144.624395      144.624395     110  OK
G2_processing_fps                 0.913996        0.913996     110  OK
G3_process_rss_mb               128.842929      128.842929      58  OK
G4_low_conf_share                 0.000000        0.000000     110  OK
G5_trace_coverage                 1.000000        1.000000     110  OK
G6_version_match_share            1.000000        1.000000     110  OK
G7_active_alerts                  0.000000        0.000000       0  OK
X1_capture_fps                    4.511415        4.511415     541  OK
X2_dropped_share                  0.796673        0.796673     541  OK
X3_process_cpu_pct              205.851724      205.851724      58  OK
X4_e2e_ms_p95                   405.366278      405.366278     110  OK
X5_confidence_psi                 9.718919        9.718919     110  OK
X6_invalid_input_rate             0.000000        0.000000     110  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/C1-20261113-103945/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/C1/inputs`
