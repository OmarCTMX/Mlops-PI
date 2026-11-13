# Despliegue en Raspberry Pi 4 (opcional)

El pipeline y el portal son Python puro + ONNX Runtime CPU, por lo que corren en Raspberry Pi OS 64 bits.

```bash
sudo apt update && sudo apt install -y python3-venv python3-pip git libgl1
git clone <url-del-repo> Mlops-PI && cd Mlops-PI
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> En aarch64 puede que no existan exactamente las mismas versiones fijadas en `requirements.txt` para todos los
> paquetes. Si `pip` no encuentra alguna, instala la versión disponible más cercana y **registra el entorno real**
> (queda automáticamente en `runs.model_identity_json` → portal `/runs/<run_id>`).

## Uso

- Fuente: la app *IP Webcam* del celular (misma red). Ajusta `source.url` en `config/config.yaml`.
- Inferencia en la Pi:

```bash
.venv/bin/python -m cvmon check-source
.venv/bin/python -m cvmon run --scenario PI-C1 --duration 120 --data-dir data-pi
.venv/bin/python -m cvmon portal --host 0.0.0.0 --port 8000 --data-dir data-pi
```

- Abre `http://<ip-de-la-pi>:8000` desde la PC o el celular. **Sin autenticación**: úsalo solo en una red de confianza.

## Qué aporta a las métricas

- G3: RAM/CPU del proceso medidos en el hardware edge real (mismo `psutil`).
- G1/G2: tiempos de inferencia y FPS comparables contra los de la PC (la diferencia se reporta con
  `python -m cvmon metrics --run <run_id>`).

Los resultados de la Pi **no sustituyen** a la evidencia de C1/C2 de la PC; son un complemento declarado como tal.
