# Evidencia · S4 · run `S4-20261113-105503`

## Identidad de la ejecución

- Escenario: `S4`  · inicio 2026-11-13T16:55:03.629Z · fin 2026-11-13T16:56:03.657Z
- Commit del código: `9b6c31e3e6aa92ad73c77065af3ed66c22fcc04b` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `ff7073511cfde98f` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (ipwebcam)
- Modelo: `mobilenetv2-12` / `mobilenetv2-7` sha256 `C1C513582D56AFCEFF8516C73804E484C81C6A830712AB6D682253F4A3CD042F`
- Notas: S4 cambio de version: se despliega mobilenetv2-7 mientras expected_version=mobilenetv2-12; misma escena de C1

## Resultados

- Eventos: 57 · por zona/estado: {"accepted": 34, "doubt": 20, "low": 3}
- Alertas: 1

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |
| `A-S4-20261113-105503-0001` | R-VERSION | medium | active | 5 de los últimos 5 eventos reportan versión ['mobilenetv2-7'] distinta de la esperada 'mobilenetv2-12' |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 57 inferencias ok; sha256 del run C1C513582D56… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 57/57 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 27/27 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 1 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | firing=6, insufficient_evidence=5, ok=23 |
| S4.a | Se detectó la versión distinta de la esperada (alerta R-VERSION) | PASA | 1 alertas |
| S4.b | Todos los eventos reportan una versión distinta de la esperada | PASA | esperada=mobilenetv2-12, reportada=mobilenetv2-7, 57/57 |
| S4.c | El artefacto desplegado es realmente otro (sha256 distinto al de C1/C2/REF) | PASA | sha256 S4 C1C513582D56… |
| S4.d | La métrica G6 refleja la discrepancia (proporción 0) | PASA | 0.0 |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Alerta `A-S4-20261113-105503-0001` (regla R-VERSION, config `ff7073511cfde98f`):
- evento `E-S4-20261113-105503-000001` · computer keyboard, keypad 0.773 · zona accepted · captura `data/captures/S4-20261113-105503/E-S4-20261113-105503-000001.jpg` · existe: True
- evento `E-S4-20261113-105503-000002` · computer keyboard, keypad 0.7519 · zona accepted · captura `-` · existe: None
- evento `E-S4-20261113-105503-000003` · computer keyboard, keypad 0.6938 · zona doubt · captura `data/captures/S4-20261113-105503/E-S4-20261113-105503-000003.jpg` · existe: True
- evento `E-S4-20261113-105503-000004` · computer keyboard, keypad 0.6769 · zona doubt · captura `data/captures/S4-20261113-105503/E-S4-20261113-105503-000004.jpg` · existe: True
- evento `E-S4-20261113-105503-000005` · computer keyboard, keypad 0.7439 · zona accepted · captura `-` · existe: None

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para S4-20261113-105503

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95               7.978440        7.978440      57  OK
G2_processing_fps                 0.941278        0.941278      57  OK
G3_process_rss_mb               128.877109      128.877109      29  OK
G4_low_conf_share                 0.052632        0.052632      57  OK
G5_trace_coverage                 1.000000        1.000000      57  OK
G6_version_match_share            0.000000        0.000000      57  OK
G7_active_alerts                  1.000000        1.000000       1  OK
X1_capture_fps                    4.655728        4.655728     278  OK
X2_dropped_share                  0.794964        0.794964     278  OK
X3_process_cpu_pct              307.982759      307.982759      29  OK
X4_e2e_ms_p95                   242.786694      242.786694      57  OK
X5_confidence_psi                 0.629374        0.629374      57  OK
X6_invalid_input_rate             0.000000        0.000000      57  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/S4-20261113-105503/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/S4/inputs`
