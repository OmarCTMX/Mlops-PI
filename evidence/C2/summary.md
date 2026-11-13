# Evidencia · C2 · run `C2-20261113-104622`

## Identidad de la ejecución

- Escenario: `C2`  · inicio 2026-11-13T16:46:22.791Z · fin 2026-11-13T16:48:23.015Z
- Commit del código: `d5f99ba506822917503c6ae9edea3751da69bcbc` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `14f760df47efe344` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (ipwebcam)
- Modelo: `mobilenetv2-12` / `mobilenetv2-12` sha256 `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5`
- Notas: C2 baja confianza: video de Nueva York reproducido en otro celular frente a la camara (escena fuera del vocabulario de ImageNet). Misma configuracion que C1.

## Resultados

- Eventos: 110 · por zona/estado: {"low": 109, "doubt": 1}
- Alertas: 2

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |
| `A-C2-20261113-104622-0001` | R-LOWCONF | high | active | 6 de las últimas 6 inferencias con puntuación cayeron en baja confianza (proporción 1.00 >= 0.5; umbral inferior 0.6) |
| `A-C2-20261113-104622-0002` | R-SHIFT | medium | active | La confianza media reciente (0.224, n=14) cayó 0.537 por debajo de la referencia (0.761); delta configurado 0.15, sostenida durante 5 evaluaciones consecutivas |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 110 inferencias ok; sha256 del run C0C3F76D93FA… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 110/110 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 110/110 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 2 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | firing=21, insufficient_evidence=5, ok=34, pending=1 |
| C2.a | Hay inferencias reales en zona de baja confianza (>= 6) | PASA | 109 eventos low |
| C2.b | Las capturas de baja confianza se conservaron y están vinculadas | PASA | 109/109 |
| C2.c | La alerta R-LOWCONF se generó según su regla declarada y enlaza eventos low | PASA | 1 alertas |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Alerta `A-C2-20261113-104622-0001` (regla R-LOWCONF, config `14f760df47efe344`):
- evento `E-C2-20261113-104622-000001` · bookshop, bookstore, bookstall 0.3164 · zona low · captura `data/captures/C2-20261113-104622/E-C2-20261113-104622-000001.jpg` · existe: True
- evento `E-C2-20261113-104622-000002` · bookshop, bookstore, bookstall 0.134 · zona low · captura `data/captures/C2-20261113-104622/E-C2-20261113-104622-000002.jpg` · existe: True
- evento `E-C2-20261113-104622-000003` · tobacco shop, tobacconist shop, tobacconist 0.1465 · zona low · captura `data/captures/C2-20261113-104622/E-C2-20261113-104622-000003.jpg` · existe: True
- evento `E-C2-20261113-104622-000004` · bobsled, bobsleigh, bob 0.1284 · zona low · captura `data/captures/C2-20261113-104622/E-C2-20261113-104622-000004.jpg` · existe: True
- evento `E-C2-20261113-104622-000005` · tobacco shop, tobacconist shop, tobacconist 0.1162 · zona low · captura `data/captures/C2-20261113-104622/E-C2-20261113-104622-000005.jpg` · existe: True

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para C2-20261113-104622

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95             134.700505      134.700505     110  OK
G2_processing_fps                 0.923059        0.923059     110  OK
G3_process_rss_mb               129.332781      129.332781      57  OK
G4_low_conf_share                 0.990909        0.990909     110  OK
G5_trace_coverage                 1.000000        1.000000     110  OK
G6_version_match_share            1.000000        1.000000     110  OK
G7_active_alerts                  2.000000        2.000000       2  OK
X1_capture_fps                    4.503182        4.503182     537  OK
X2_dropped_share                  0.795158        0.795158     537  OK
X3_process_cpu_pct              222.957895      222.957895      57  OK
X4_e2e_ms_p95                   457.169032      457.169032     110  OK
X5_confidence_psi                12.954976       12.954976     110  OK
X6_invalid_input_rate             0.000000        0.000000     110  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/C2-20261113-104622/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/C2/inputs`
