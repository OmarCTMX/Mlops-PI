# Evidencia · S2 · run `S2-20261113-110107`

## Identidad de la ejecución

- Escenario: `S2`  · inicio 2026-11-13T17:01:07.218Z · fin 2026-11-13T17:03:37.310Z
- Commit del código: `0771e330976ade4c33b5091aff0d05bbaa0413a9` (árbol con cambios sin confirmar al ejecutar)
- Configuración: hash `14f760df47efe344` (copia en `exports/config_snapshots.jsonl`)
- Fuente: `phone-ipwebcam-01` (ipwebcam)
- Modelo: `mobilenetv2-12` / `mobilenetv2-12` sha256 `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5`
- Notas: S2 cambio sostenido: ~40 s teclado (escena de referencia) y luego video de Nueva York sostenido hasta el final

## Resultados

- Eventos: 144 · por zona/estado: {"accepted": 53, "low": 88, "doubt": 3}
- Alertas: 2

| Alerta | Regla | Severidad | Estado | Motivo |
| --- | --- | --- | --- | --- |
| `A-S2-20261113-110107-0001` | R-LOWCONF | high | active | 5 de las últimas 10 inferencias con puntuación cayeron en baja confianza (proporción 0.50 >= 0.5; umbral inferior 0.6) |
| `A-S2-20261113-110107-0002` | R-SHIFT | medium | active | La confianza media reciente (0.382, n=15) cayó 0.379 por debajo de la referencia (0.761); delta configurado 0.15, sostenida durante 5 evaluaciones consecutivas |

## Verificaciones automáticas

| ID | Verificación | Resultado | Detalle |
| --- | --- | --- | --- |
| V1 | Inferencias reales atribuibles a un modelo identificado | PASA | 144 inferencias ok; sha256 del run C0C3F76D93FA… coincide con el archivo del repo |
| V2 | Confianza y clase coinciden con la salida top-k del modelo (no inyectadas) | PASA | 144/144 eventos consistentes |
| V3 | Capturas vinculadas existen en disco (sin expiración automática) | PASA | 97/97 capturas resuelven |
| V4 | Cada alerta enlaza regla, configuración, eventos, motivo, severidad y acción | PASA | 2 alertas |
| V5 | Métricas recalculadas de forma independiente coinciden con las almacenadas | PASA | 13/13 |
| V6 | Las reglas registraron evaluaciones (incluida la evidencia insuficiente) | PASA | firing=20, insufficient_evidence=5, ok=52, pending=1 |
| S2.a | Se disparó la regla de cambio sostenido R-SHIFT | PASA | 1 alertas |
| S2.b | La alerta registra la caída frente a la referencia y la persistencia | PASA |  |
| S2.c | Hubo evidencia suficiente previa (no se disparó con datos insuficientes) | PASA | 52 inferencias previas |

## Cadena de una muestra (fuente → modelo → evento → captura → alerta)

Alerta `A-S2-20261113-110107-0001` (regla R-LOWCONF, config `14f760df47efe344`):
- evento `E-S2-20261113-110107-000037` · computer keyboard, keypad 0.9439 · zona accepted · captura `-` · existe: None
- evento `E-S2-20261113-110107-000038` · computer keyboard, keypad 0.9549 · zona accepted · captura `-` · existe: None
- evento `E-S2-20261113-110107-000039` · computer keyboard, keypad 0.9495 · zona accepted · captura `-` · existe: None
- evento `E-S2-20261113-110107-000040` · computer keyboard, keypad 0.9493 · zona accepted · captura `-` · existe: None
- evento `E-S2-20261113-110107-000041` · computer keyboard, keypad 0.9072 · zona accepted · captura `data/captures/S2-20261113-110107/E-S2-20261113-110107-000041.jpg` · existe: True

## Recálculo independiente de métricas

```
Recálculo independiente de métricas para S2-20261113-110107

metric_id                       almacenado     recalculado       n  resultado
G1_inference_ms_p95               8.284055        8.284055     144  OK
G2_processing_fps                 0.958698        0.958698     144  OK
G3_process_rss_mb               127.885478      127.885478      74  OK
G4_low_conf_share                 0.611111        0.611111     144  OK
G5_trace_coverage                 1.000000        1.000000     144  OK
G6_version_match_share            1.000000        1.000000     144  OK
G7_active_alerts                  2.000000        2.000000       2  OK
X1_capture_fps                    4.759566        4.759566     712  OK
X2_dropped_share                  0.797753        0.797753     712  OK
X3_process_cpu_pct              306.887838      306.887838      74  OK
X4_e2e_ms_p95                   222.614610      222.614610     144  OK
X5_confidence_psi                 8.877210        8.877210     144  OK
X6_invalid_input_rate             0.000000        0.000000     144  OK

Coinciden 13/13 métricas
```

## Archivos

- `exports/*.jsonl`: observaciones primarias (eventos, stream, recursos, alertas, evaluaciones, métricas)
- Capturas: `data/captures/S2-20261113-110107/`
- `recalc.txt`, `verification.json`: salidas de los comandos de verificación
- Entradas reproducibles (bytes originales de la fuente): `evidence/S2/inputs`
