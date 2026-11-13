# Capturas de pantalla del portal

Guarda aquí capturas **reales** del portal (resolución completa) con estos nombres. `python -m cvmon index` usa su
existencia para marcar las funcionalidades adicionales como demostradas.

| Archivo | Qué debe verse |
| --- | --- |
| `events.png` | `/events` con eventos de C1 o C2 (columnas de identidad, estado, confianza, zona y captura) |
| `event-detail.png` | `/events/<id>` de un evento de baja confianza con su imagen y alertas vinculadas |
| `alerts.png` | `/alerts` mostrando momento, motivo, severidad y acción sugerida |
| `alert-detail.png` | `/alerts/<id>` con la regla, la observación y los eventos vinculados |
| `metrics.png` | `/metrics?run=<C1>` con G1–G7 y adicionales |
| `live.png` | `/live` con el pipeline en ejecución (frame + predicción) |
| `dashboard.png` | `/?run=<run>` con las 4 gráficas |
| `events-filtered.png` | `/events` con filtros aplicados (por ejemplo zona = baja) y el enlace de exportación |
| `gallery-review.png` | `/gallery` con al menos una captura revisada manualmente |
| `runs.png` | `/runs/<run_id>` con la identidad del modelo |
