# Evidencia · C1 · run `C1-20261113-095839`

## Identidad de la ejecución

- Escenario: `C1`  · inicio 2026-11-13T15:58:39.148Z · fin 2026-11-13T16:00:39.208Z
- Commit del código: `d5f99ba506822917503c6ae9edea3751da69bcbc` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `14f760df47efe344` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (ipwebcam)
- Modelo: `mobilenetv2-12` / `mobilenetv2-12` sha256 `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5`
- Notas: C1 operacion normal: misma escena de la referencia (teclado, vista superior, celular fijo)

## Resultados

- Eventos: 114 · por zona/estado: {"low": 5, "doubt": 6, "accepted": 103}
- Alertas: 2

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |
| `A-C1-20261113-095839-0001` | R-LOWCONF | high | resolved | 5 de las últimas 6 inferencias con puntuación cayeron en baja confianza (proporción 0.83 >= 0.5; umbral inferior 0.6) |
| `A-C1-20261113-095839-0002` | R-SHIFT | medium | resolved | La confianza media reciente (0.561, n=14) cayó 0.199 por debajo de la referencia (0.761); delta configurado 0.15, sostenida durante 5 evaluaciones consecutivas |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 114 inferencias ok; sha256 del run C0C3F76D93FA… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 114/114 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 22/22 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 2 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | firing=2, insufficient_evidence=5, ok=57, pending=1 |
| C1.a | Operación normal: hay inferencias suficientes (>= 20) y zona aceptada observada | PASA | ok=114 zonas={'accepted': 103, 'doubt': 6, 'low': 5} |
| C1.b | Operación normal: la baja confianza no domina (< 20 % de las inferencias) | PASA | baja=0.04 |
| C1.c | Sin alerta de baja confianza durante la operación normal | FALLA | 1 alertas R-LOWCONF |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Alerta `A-C1-20261113-095839-0001` (regla R-LOWCONF, config `14f760df47efe344`):
- evento `E-C1-20261113-095839-000001` · mailbag, postbag 0.2319 · zona low · captura `data/captures/C1-20261113-095839/E-C1-20261113-095839-000001.jpg` · existe: True
- evento `E-C1-20261113-095839-000002` · wallet, billfold, notecase, pocketbook 0.2806 · zona low · captura `data/captures/C1-20261113-095839/E-C1-20261113-095839-000002.jpg` · existe: True
- evento `E-C1-20261113-095839-000003` · jean, blue jean, denim 0.093 · zona low · captura `data/captures/C1-20261113-095839/E-C1-20261113-095839-000003.jpg` · existe: True
- evento `E-C1-20261113-095839-000004` · mouse, computer mouse 0.0518 · zona low · captura `data/captures/C1-20261113-095839/E-C1-20261113-095839-000004.jpg` · existe: True
- evento `E-C1-20261113-095839-000005` · space bar 0.5853 · zona low · captura `data/captures/C1-20261113-095839/E-C1-20261113-095839-000005.jpg` · existe: True

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para C1-20261113-095839

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95              96.318550       96.318550     114  OK
G2_processing_fps                 0.947907        0.947907     114  OK
G3_process_rss_mb               128.234461      128.234461      58  OK
G4_low_conf_share                 0.043860        0.043860     114  OK
G5_trace_coverage                 1.000000        1.000000     114  OK
G6_version_match_share            1.000000        1.000000     114  OK
G7_active_alerts                  0.000000        0.000000       2  OK
X1_capture_fps                    4.557142        4.557142     546  OK
X2_dropped_share                  0.791209        0.791209     546  OK
X3_process_cpu_pct              275.444828      275.444828      58  OK
X4_e2e_ms_p95                   419.450033      419.450033     114  OK
X5_confidence_psi                 0.956557        0.956557     114  OK
X6_invalid_input_rate             0.000000        0.000000     114  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/C1-20261113-095839/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/C1/inputs`
