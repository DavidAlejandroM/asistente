# Montaje en la Raspberry Pi Zero 2 W

El orquestador corre aquí; el PC aloja Ollama + STT + TTS (ver `services/`).

## 1. Sistema

Raspberry Pi OS Lite **64-bit** (Bookworm). Tras el primer arranque:

```bash
sudo apt update && sudo apt install -y \
  python3-venv python3-dev libportaudio2 libatlas-base-dev \
  pipewire pipewire-pulse wireplumber bluez
```

Conecta un **micrófono USB** (la Zero 2 W no tiene entrada de audio).

## 2. Instalar el asistente

```bash
git clone <repo> ~/asistente && cd ~/asistente
python3 -m venv .venv
.venv/bin/pip install -e ".[audio,admin]"
```

`webrtcvad-wheels`, `openwakeword` y `sounddevice` traen wheels para ARM64.
openWakeWord usa `tflite-runtime`; si no se instaló solo:

```bash
.venv/bin/pip install tflite-runtime || .venv/bin/pip install onnxruntime
```

(con `onnxruntime`, pon `wakeword.framework: onnx` en `config.yaml`).

## 3. Configurar

```bash
cp config.example.yaml config.yaml
```

Edita `config.yaml`:

- `llm/stt/tts.url` → IP del PC en la LAN.
- `audio.input_device` → nombre del micro USB. Lista los dispositivos con:
  ```bash
  .venv/bin/python -c "import sounddevice; print(sounddevice.query_devices())"
  ```
- `audio.output_device` → el altavoz (ver paso 5 para Bluetooth).

Prueba sin wake word:

```bash
.venv/bin/python -m asistente --text          # teclado, contra el PC
.venv/bin/python -m asistente --once -v        # un ciclo con micro real
```

Abre la UI de administración en `http://<ip-de-la-pi>:8080`.

## 4. Servicio systemd

```bash
sudo cp systemd/asistente.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asistente
journalctl -u asistente -f
```

## 5. Altavoz Bluetooth

```bash
bluetoothctl
> power on
> scan on
> pair <MAC>
> trust <MAC>
> connect <MAC>
```

Con PipeWire el altavoz aparece como salida; pon su nombre en `audio.output_device`
o déjalo en `null` para usar el predeterminado. Para reconexión automática al arrancar
ver `systemd/bt-autoconnect.service`.

> ⚠️ En la Zero 2 W el WiFi y el Bluetooth comparten antena: si el audio A2DP se
> entrecorta mientras habla con el PC, usa un mini-dongle USB de audio con un altavoz
> por cable, o un dongle Bluetooth USB aparte.

## 6. Spotify (opcional)

Ver `services/README.md` y `scripts/spotify_auth.py`. `librespot`/`spotifyd` corre como
servicio aparte en la Pi y saca el audio al altavoz Bluetooth.
