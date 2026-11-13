# Extras reclamados (sin doble conteo con la base)

Estado calculado por `python -m cvmon index` a partir de las verificaciones reales. “Pendiente” = aún sin evidencia que lo respalde; no se reclama.

## Escenarios adicionales (S)

| ID | Escenario | Nivel solicitado | Evidencia | Estado |
| --- | --- | --- | --- | --- |
| S1 | Interrupción del stream y recuperación (fallo → alerta R‑STALE → reconexión → verificación posterior) | 10 | `evidence/S1/` | DEMOSTRADO — todas las verificaciones pasan |
| S2 | Cambio sostenido de confianza frente a la referencia (R‑SHIFT) | 8 | `evidence/S2/` | DEMOSTRADO — todas las verificaciones pasan |
| S3 | Entradas inválidas (imágenes corruptas) sin detener el pipeline | 5 | `evidence/S3/` | DEMOSTRADO — todas las verificaciones pasan |
| S4 | Cambio de versión del modelo (dos artefactos reales; alerta R‑VERSION) | 5 | `evidence/S4/` | DEMOSTRADO — todas las verificaciones pasan |

Notas: C2 (baja confianza aislada) **no** se reclama como drift; S2 es otra secuencia con transición y persistencia.

## Métricas adicionales (M)

| ID | Métrica | Nivel | Valor (run de referencia) | Condición del nivel | Estado |
| --- | --- | --- | --- | --- | --- |
| M1 | `X1_capture_fps` FPS de captura | 5 | 4.511 (n=541, `C1-20261113-103945`) | tasa derivada, recálculo comprobable | DEMOSTRADO |
| M2 | `X2_dropped_share` descartes por motivo | 5 | 0.7967 (n=541, `C1-20261113-103945`) | proporción con motivos separados | DEMOSTRADO |
| M3 | `X3_process_cpu_pct` CPU del proceso | 3 | 205.9 (n=58, `C1-20261113-103945`) | agregado sencillo | DEMOSTRADO |
| M4 | `X4_e2e_ms_p95` latencia extremo a extremo | 5 | 405.4 (n=110, `C1-20261113-103945`) | percentil por etapas, recalculable | DEMOSTRADO |
| M5 | `X5_confidence_psi` PSI vs referencia | 8 si el caso controlado muestra el cambio (PSI C1 < 0.1 ≤ PSI S2), si no 5 | C1: 9.719 (n=110, `C1-20261113-103945`); S2: 8.877 (n=144, `S2-20261113-110107`) | comparación con la referencia + caso controlado | DEMOSTRADO nivel 5 (sin caso controlado) |
| M6 | `X6_invalid_input_rate` entradas inválidas | 5 | 0.1 (n=30, `S3-20261113-104951`) | proporción, verificada en S3 | DEMOSTRADO |

Ninguna de estas métricas es la métrica base de su grupo (ver `docs/inventario-metricas.md`).

## Funcionalidades adicionales (F)

| ID | Funcionalidad | Nivel | Evidencia | Estado |
| --- | --- | --- | --- | --- |
| F1 | Visualización del stream en vivo con la predicción (`/live`, `/api/live`) | 5 | `tests/test_portal.py`, `evidence/portal/live.png` | DEMOSTRADO |
| F2 | Dashboard con gráficas históricas por run (`/`, `/api/series`): confianza con umbrales, zonas, histograma vs referencia, latencia; selección de run, estado vacío y de error | 10 | `tests/test_portal.py`, `evidence/portal/dashboard.png` | DEMOSTRADO |
| F3 | Filtros avanzados de eventos/alertas (11 criterios validados) y exportación CSV/JSON del resultado filtrado, con errores 400 y estado vacío | 10 | `tests/test_portal.py`, `evidence/portal/events-filtered.png` | DEMOSTRADO |
| F4 | Revisión manual de capturas (galería, veredicto y nota persistidos, filtro por revisión, redirección segura) | 10 | `tests/test_portal.py`, `evidence/portal/gallery-review.png` | DEMOSTRADO |

## Totales

El total sumado se calcula con los elementos en estado DEMOSTRADO; no hay tope ni normalización. Los puntos de la base (R1–R7) se evalúan por separado.
