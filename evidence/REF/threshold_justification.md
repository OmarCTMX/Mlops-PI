# Justificación de umbrales (R3.1)

- Modelo: `mobilenetv2-12` versión `mobilenetv2-12` (sha256 `C0C3F76D93FA…`)
- Observaciones de referencia: n = 167 (runs: REF-20261113-094929)
- Construida: 2026-11-13T15:52:31.199Z

## Distribución de confianza top-1 en condiciones de referencia

| Estadístico | Valor |
| --- | --- |
| media | 0.7609 |
| desviación estándar | 0.0804 |
| mínimo / máximo | 0.2908 / 0.8954 |
| P05 | 0.6186 |
| P10 | 0.6540 |
| P25 | 0.7305 |
| P50 | 0.7827 |
| P75 | 0.8110 |
| P90 | 0.8305 |
| P95 | 0.8436 |

## Regla de elección

- Umbral superior = P25 de la referencia (redondeado hacia abajo a múltiplos de 0.05): se espera que ~75 % de las observaciones normales queden aceptadas.
- Umbral inferior = P05 de la referencia (redondeado hacia abajo): solo ~5 % de las observaciones normales deberían caer en baja confianza, de modo que una proporción alta sea señal de cambio.
- Valores que produce la regla con esta referencia: inferior = 0.60, superior = 0.70.
- **Valores configurados**: inferior = 0.60, superior = 0.70 (coinciden con la regla).

## Reparto de la referencia con los umbrales configurados

| Zona | Condición | Observaciones | Proporción |
| --- | --- | --- | --- |
| accepted | s >= 0.70 | 138 | 0.826 |
| doubt | 0.60 <= s < 0.70 | 24 | 0.144 |
| low | s < 0.60 | 5 | 0.030 |

## Límites

- La confianza es la probabilidad softmax de la clase top-1; no es probabilidad de acierto ni se calibró formalmente (no se exige).
- La referencia corresponde a UNA escena/cámara/iluminación; si cambian modelo, preprocesamiento o configuración, las series deben separarse y la referencia reconstruirse.
- Los umbrales se fijan antes de ejecutar C1 y C2 y no se modifican para aprobar escenarios.
