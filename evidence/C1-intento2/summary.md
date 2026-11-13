# Evidencia · C1 · run `C1-20261113-100136`

## Identidad de la ejecución

- Escenario: `C1`  · inicio 2026-11-13T16:01:36.649Z · fin 2026-11-13T16:03:36.854Z
- Commit del código: `d5f99ba506822917503c6ae9edea3751da69bcbc` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `14f760df47efe344` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (ipwebcam)
- Modelo: `mobilenetv2-12` / `mobilenetv2-12` sha256 `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5`
- Notas: C1 operacion normal (segundo intento): misma escena de la referencia, celular fijo sin tocar

## Resultados

- Eventos: 116 · por zona/estado: {"low": 57, "doubt": 22, "accepted": 37}
- Alertas: 3

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |
| `A-C1-20261113-100136-0001` | R-LOWCONF | high | resolved | 4 de las últimas 6 inferencias con puntuación cayeron en baja confianza (proporción 0.67 >= 0.5; umbral inferior 0.6) |
| `A-C1-20261113-100136-0002` | R-SHIFT | medium | resolved | La confianza media reciente (0.519, n=14) cayó 0.242 por debajo de la referencia (0.761); delta configurado 0.15, sostenida durante 5 evaluaciones consecutivas |
| `A-C1-20261113-100136-0003` | R-LOWCONF | high | active | 5 de las últimas 10 inferencias con puntuación cayeron en baja confianza (proporción 0.50 >= 0.5; umbral inferior 0.6) |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 116 inferencias ok; sha256 del run C0C3F76D93FA… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 116/116 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 83/83 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 3 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | firing=16, insufficient_evidence=5, ok=45, pending=2 |
| C1.a | Operación normal: hay inferencias suficientes (>= 20) y zona aceptada observada | PASA | ok=116 zonas={'accepted': 37, 'doubt': 22, 'low': 57} |
| C1.b | Operación normal: la baja confianza no domina (< 20 % de las inferencias) | FALLA | baja=0.49 |
| C1.c | Sin alerta de baja confianza durante la operación normal | FALLA | 2 alertas R-LOWCONF |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Alerta `A-C1-20261113-100136-0001` (regla R-LOWCONF, config `14f760df47efe344`):
- evento `E-C1-20261113-100136-000001` · Band Aid 0.405 · zona low · captura `data/captures/C1-20261113-100136/E-C1-20261113-100136-000001.jpg` · existe: True
- evento `E-C1-20261113-100136-000002` · Band Aid 0.6857 · zona doubt · captura `data/captures/C1-20261113-100136/E-C1-20261113-100136-000002.jpg` · existe: True
- evento `E-C1-20261113-100136-000003` · Band Aid 0.5473 · zona low · captura `data/captures/C1-20261113-100136/E-C1-20261113-100136-000003.jpg` · existe: True
- evento `E-C1-20261113-100136-000004` · Band Aid 0.4053 · zona low · captura `data/captures/C1-20261113-100136/E-C1-20261113-100136-000004.jpg` · existe: True
- evento `E-C1-20261113-100136-000005` · Band Aid 0.6428 · zona doubt · captura `data/captures/C1-20261113-100136/E-C1-20261113-100136-000005.jpg` · existe: True

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para C1-20261113-100136

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95              80.156125       80.156125     116  OK
G2_processing_fps                 0.966089        0.966089     116  OK
G3_process_rss_mb               127.754946      127.754946      58  OK
G4_low_conf_share                 0.491379        0.491379     116  OK
G5_trace_coverage                 1.000000        1.000000     116  OK
G6_version_match_share            1.000000        1.000000     116  OK
G7_active_alerts                  1.000000        1.000000       3  OK
X1_capture_fps                    4.839572        4.839572     580  OK
X2_dropped_share                  0.800000        0.800000     580  OK
X3_process_cpu_pct              278.044828      278.044828      58  OK
X4_e2e_ms_p95                   273.757815      273.757815     116  OK
X5_confidence_psi                 2.326474        2.326474     116  OK
X6_invalid_input_rate             0.000000        0.000000     116  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/C1-20261113-100136/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/C1/inputs`
