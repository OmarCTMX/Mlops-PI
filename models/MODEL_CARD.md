# Ficha del modelo (R1.3, R7.3)

| Campo | Valor |
| --- | --- |
| Tarea | Clasificación de imágenes (ImageNet-1k, 1000 clases) |
| Arquitectura | MobileNetV2 (apta para Raspberry Pi 4, CPU) |
| Artefacto principal | `models/mobilenetv2-12.onnx` (opset 12) |
| `model_id` / versión declarada | `mobilenetv2-12` / `mobilenetv2-12` |
| SHA-256 | `C0C3F76D93FA3FD6580652A45618618A220FCED18BABF65774ED169DE0432AD5` |
| Tamaño | 13 964 571 bytes |
| Clases | `models/synset.txt` (1000 líneas `nXXXXXXXX etiqueta`) |
| Entrada | `input` float32 `[N,3,224,224]` |
| Salida | `output` float32 `[N,1000]` (logits) |
| Entorno de ejecución | ONNX Runtime (`CPUExecutionProvider`), versión fijada en `requirements.txt`; el entorno real de cada run queda en `runs.model_identity_json` y se muestra en `/runs/<run_id>` |

## Procedencia (declaración)

- Modelo **preentrenado y sin reentrenar**, tomado del **ONNX Model Zoo** (`github.com/onnx/models`,
  `validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx`), descargado sin modificaciones.
- Etiquetas: `validated/vision/classification/synset.txt` del mismo repositorio.
- No se reutiliza ningún modelo, código ni datos del Proyecto 5 (Equipo03). Todo el código de `cvmon/` es de
  autoría individual del estudiante (con asistencia de un agente de IA, declarada en el README).

## Artefacto alterno (solo escenario S4, cambio de versión)

| Campo | Valor |
| --- | --- |
| Archivo | `models/mobilenetv2-7.onnx` (opset 7) |
| SHA-256 | `C1C513582D56AFCEFF8516C73804E484C81C6A830712AB6D682253F4A3CD042F` |
| Origen | ONNX Model Zoo, mismo directorio `mobilenet/model/` |
| Uso | Se despliega con `model.version = mobilenetv2-7` mientras la configuración espera `mobilenetv2-12` |

## Preprocesamiento (idéntico para ambos artefactos)

`BGR→RGB`; redimensionar el lado corto a 256 (`cv2.INTER_LINEAR`); recorte central 224×224; escala `/255`;
normalización `mean=[0.485,0.456,0.406]`, `std=[0.229,0.224,0.225]`; tensor `NCHW float32`.

## Tipo de clasificación y aplicación de la política

**Multiclase, una etiqueta por imagen** (softmax sobre 1000 clases mutuamente excluyentes). La política de dos umbrales
se aplica a **la puntuación de la clase top‑1** de cada imagen; el top‑5 se conserva en el evento (`topk_json`) solo
como contexto. Se clasifica la imagen completa (recorte central 224×224), no recortes de objetos.

## Definición de “confianza”

Probabilidad **softmax** de la clase top‑1 sobre los logits. Es una puntuación de salida del modelo:
**no** es probabilidad de acierto ni se calibró formalmente (la rúbrica no lo exige).

## Límites

- ImageNet‑1k no contiene todas las clases posibles de una escena real; baja confianza puede indicar un objeto
  fuera del vocabulario, mala iluminación, desenfoque u oclusión.
- No se evalúa calidad predictiva (accuracy, F1, mAP…): no se dispone ni se exigen etiquetas reales.
