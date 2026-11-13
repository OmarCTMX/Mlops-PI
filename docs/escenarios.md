# Escenarios: preparación y comandos (R6 y extras)

Todos los comandos se ejecutan desde la raíz del repo en **PowerShell**. Ninguno inyecta puntuaciones: el modelo
procesa imágenes reales de la cámara (o de las entradas que esa cámara guardó).

## 0. Preparar el celular (IP Webcam)

1. Instala **IP Webcam** (Android). Conecta el celular y la PC a la **misma red Wi‑Fi**.
2. En la app: resolución de video **640×480** (menos tamaño de capturas), *Start server*. Anota la URL
   (por ejemplo `http://192.168.1.50:8080`).
3. Edita `config/config.yaml` → `source.url` con esa URL.
4. Fija el teléfono (tripié/libro). Verifica la fuente y el modelo con un frame:

```powershell
.\.venv\Scripts\python.exe -m cvmon check-source
```

## 1. Referencia (REF) y umbrales — antes de C1/C2

Escena normal y estable con objetos que ImageNet reconozca (taza, teclado, laptop, botella…). Objetivo: **≥ 100
inferencias** (≈ 2–3 min a 1 inferencia/s).

```powershell
.\scripts\scenario.ps1 -Name REF -Duration 180
.\.venv\Scripts\python.exe -m cvmon thresholds --out evidence/REF/threshold_justification.md
```

Revisa la sugerencia (P05/P25). Si difiere de `thresholds:` en `config/config.yaml`, **actualiza esos dos valores**,
vuelve a ejecutar `thresholds` y haz commit (`config/config.yaml`, `config/reference.json`, `evidence/REF`).
**No cambies umbrales después de este punto.**

## 2. C1 · Operación normal (R6.1)

La misma escena de la referencia, cámara estable.

```powershell
.\scripts\scenario.ps1 -Name C1 -Kind C1 -Duration 120
.\scripts\replay.ps1 -Name C1
```

Esperado: ≥ 20 inferencias, zona `accepted` presente, baja confianza < 20 %, sin alerta `R-LOWCONF`.

## 3. C2 · Baja confianza (R6.2)

Durante los 120 s, **cambia la escena sin tocar el software**: apunta a una pared lisa/oscura, tapa parcialmente el lente,
desenfoca (mueve el celular) o muestra algo que ImageNet no reconozca. Las puntuaciones bajas deben salir del modelo.

```powershell
.\scripts\scenario.ps1 -Name C2 -Kind C2 -Duration 120
.\scripts\replay.ps1 -Name C2
```

Esperado: ≥ 6 eventos `low` con captura, y alerta `R-LOWCONF` vinculada a esos eventos. Si el modelo no produce
casos bajos, **registra el límite** y busca otra entrada; nunca modifiques puntuaciones.

## 4. Escenarios adicionales

| Escenario | Qué hacer | Comando |
| --- | --- | --- |
| **S1 interrupción y recuperación** (10) | Con el pipeline corriendo, a los ~30 s detén *IP Webcam* (o apaga el Wi‑Fi del celular) ~25 s y reanúdalo. | `.\scripts\scenario.ps1 -Name S1 -Kind S1 -Duration 120` |
| **S2 cambio sostenido de confianza** (8) | 40 s de escena de referencia y luego ≥ 60 s con un cambio moderado y sostenido (poca luz, otro objeto) hasta que `R-SHIFT` dispare. | `.\scripts\scenario.ps1 -Name S2 -Kind S2 -Duration 150` |
| **S3 entrada inválida** (5) | Crea una secuencia con imágenes reales de C1 y 3 archivos JPEG truncados (ver abajo). | ver abajo |
| **S4 cambio de versión** (5) | Despliega el artefacto alterno `mobilenetv2-7` esperando `mobilenetv2-12`. | ver abajo |

S3 (la corrupción del archivo es la falla de entrada; el modelo sigue siendo real para las imágenes válidas):

```powershell
New-Item -ItemType Directory -Force evidence/S3/inputs_src | Out-Null
Copy-Item evidence/C1/inputs/000*.jpg evidence/S3/inputs_src/      # imágenes reales guardadas en C1
$f = Get-ChildItem evidence/S3/inputs_src/*.jpg | Select-Object -First 3
foreach ($x in $f) { $b = [IO.File]::ReadAllBytes($x.FullName); [IO.File]::WriteAllBytes($x.FullName, $b[0..([int]($b.Length/3))]) }   # trunca 3 imágenes
.\scripts\scenario.ps1 -Name S3 -Kind S3 -Duration 60 -Set source.type=sequence,source.path=evidence/S3/inputs_src,source.capture_fps=2,sampling.sample_interval_s=0
```

S4 (dos artefactos reales distintos; la versión reportada difiere de la esperada ⇒ `R-VERSION`):

```powershell
.\scripts\scenario.ps1 -Name S4 -Kind S4 -Duration 60 -Set model.path=models/mobilenetv2-7.onnx,model.sha256=C1C513582D56AFCEFF8516C73804E484C81C6A830712AB6D682253F4A3CD042F,model.version=mobilenetv2-7
```

## 5. Portal y capturas de pantalla

```powershell
.\.venv\Scripts\python.exe -m cvmon portal            # http://127.0.0.1:8000
```

Guarda capturas en `evidence/portal/` (nombres sugeridos en `evidence/portal/README.md`).
El stream en vivo (`/live`) solo muestra algo mientras un `run` está en ejecución.

## 6. Cierre

```powershell
.\.venv\Scripts\python.exe -m cvmon index          # genera evidence/INDEX.md
.\.venv\Scripts\python.exe -m pytest -q
git add -A; git commit -m "Evidencias C1/C2 y extras"
```
