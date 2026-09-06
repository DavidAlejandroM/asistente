# Montaje en la Raspberry Pi Zero 2 W

El **orquestador** corre en la Pi (captura de audio, wake word, skills, UI de
administración). Los modelos pesados corren en el **PC** de la LAN: Ollama + STT
(faster-whisper) + TTS (Piper), levantados con `services/docker-compose.yml`.

```text
Pi Zero 2 W:  micro USB → wake word → grabador(VAD) → [STT] → cerebro(LLM+skills) → [TTS] → altavoz
PC (LAN):     Ollama :11434   ·   STT :8001   ·   TTS :8002
```

Antes de empezar: ten el PC con los servicios corriendo y anota su IP
(`ip addr` en el PC). Comprueba desde otro equipo: `curl http://IP_PC:8001/health`.

---

## 1. Sistema operativo

Graba **Raspberry Pi OS Lite (64-bit)**, Bookworm, con Raspberry Pi Imager.
En el Imager configura ya: hostname, usuario, WiFi y SSH.

Tras el primer arranque, por SSH:

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git python3-venv python3-dev \
  libportaudio2 portaudio19-dev libatlas-base-dev \
  pipewire pipewire-pulse wireplumber bluez
sudo reboot
```

### Hardware de audio

- **Micrófono USB** (la Zero 2 W no tiene entrada de audio). También sirve un HAT
  I2S tipo ReSpeaker 2-Mic.
- **Altavoz**: Bluetooth (paso 6) o un mini-dongle USB de audio con altavoz por cable.

Comprueba que el sistema ve el micro:

```bash
arecord -l                     # tarjetas de captura
pactl list sources short       # fuentes de PipeWire
```

---

## 2. Instalar el asistente

```bash
git clone https://github.com/DavidAlejandroM/asistente.git ~/asistente
cd ~/asistente
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[audio,admin]"
```

`sounddevice`, `openwakeword` y `webrtcvad-wheels` traen wheels para ARM64.

openWakeWord necesita un runtime de inferencia. Instala **tflite-runtime** (ligero,
recomendado en la Pi):

```bash
.venv/bin/pip install tflite-runtime
# si no hay wheel para tu Python:
.venv/bin/pip install onnxruntime        # y pon  wakeword.framework: onnx
```

Primera ejecución: openWakeWord descarga solo los modelos base (~10 MB) a
`~/.local/...` la primera vez que arranca.

---

## 3. Configurar

```bash
cp config.example.yaml config.yaml
nano config.yaml
```

Claves a ajustar:

| Sección | Qué poner |
|---|---|
| `llm.url`, `stt.url`, `tts.url` | `http://IP_DEL_PC:11434 / :8001 / :8002` |
| `llm.model` | `qwen2.5:7b` (o `qwen2.5:3b` si el PC va justo) |
| `tts.voice` | `es_ES-sharvard-medium` (o `es_ES-davefx-medium`) |
| `wakeword.model` | `hey_jarvis` de momento; ver paso 7 para uno en español |
| `wakeword.threshold` | `0.5`; súbelo si hay falsos positivos, bájalo si no te oye |
| `audio.input_device` | nombre o índice del micro USB (ver abajo) |
| `audio.output_device` | `null` = predeterminado del sistema (recomendado con Bluetooth) |
| `location` | ya viene con San Vicente Ferrer, Antioquia |
| `admin.port` | `8080` |

Listar dispositivos de audio para `input_device` / `output_device`:

```bash
.venv/bin/python -c "import sounddevice; print(sounddevice.query_devices())"
```

Puedes escribir el índice (`1`) o parte del nombre (`"USB PnP"`).

### Secretos (opcional)

```bash
cp .env.example .env && nano .env
```

- `HOME_ASSISTANT_TOKEN` — en HA: perfil → *Long-lived access tokens*.
- `SPOTIFY_*` — ver paso 8.

Las skills de HA y Spotify solo se cargan si hay credenciales; sin ellas el asistente
funciona con clima y temporizadores.

---

## 4. Probar antes de instalar el servicio

```bash
# conversación por teclado, contra el PC (no usa micro):
.venv/bin/python -m asistente --text

# un ciclo real: di la palabra de activación y una orden
.venv/bin/python -m asistente --once -v

# bucle continuo
.venv/bin/python -m asistente -v
```

Con `--text` o el bucle en marcha, abre la **UI de administración**:
`http://IP_DE_LA_PI:8080` — estado en vivo, logs, activar/desactivar skills,
temporizadores, editar `config.yaml` y botón de reinicio.

Errores típicos aquí: URL del PC mal, cortafuegos del PC, o `input_device` incorrecto.

---

## 5. Servicio systemd

Edita `systemd/asistente.service` y ajusta `User=` y las rutas (`/home/TU_USUARIO/asistente`).
Si tu uid no es 1000, corrige `XDG_RUNTIME_DIR`.

```bash
sudo cp systemd/asistente.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asistente
journalctl -u asistente -f
```

Se reinicia solo si se cae (`Restart=always`). El botón "Reiniciar servicio" de la UI
ejecuta `systemctl restart asistente`.

---

## 6. Altavoz Bluetooth

```bash
bluetoothctl
[bluetooth]# power on
[bluetooth]# scan on
[bluetooth]# pair AA:BB:CC:DD:EE:FF
[bluetooth]# trust AA:BB:CC:DD:EE:FF
[bluetooth]# connect AA:BB:CC:DD:EE:FF
[bluetooth]# quit
```

Con PipeWire el altavoz se convierte en la salida por defecto al conectarse; deja
`audio.output_device: null`. Comprueba: `speaker-test -c1 -twav`.

Reconexión automática al arrancar:

```bash
# edita la MAC en systemd/bt-autoconnect.service
sudo cp systemd/bt-autoconnect.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable bt-autoconnect
```

> ⚠️ **WiFi y Bluetooth comparten antena** en la Zero 2 W. Si el audio A2DP se
> entrecorta mientras el asistente habla con el PC:
> - usa un **mini-dongle USB de audio** + altavoz por cable (lo más fiable), o
> - un **dongle Bluetooth USB** aparte, o
> - baja el bitrate / acerca el router.

---

## 7. Palabra de activación en español (opcional)

Los modelos incorporados (`hey_jarvis`, `alexa`, `hey_mycroft`) están en inglés.
Para "oye asistente" u otra frase en español hay que **entrenar** un modelo con voz
sintética — en **Google Colab con GPU**, no en la Pi. Ver [`training/README.md`](../training/README.md).

Resultado: un `oye_asistente.tflite` de ~1 MB. En la Pi:

```bash
mkdir -p ~/asistente/models
# copia el .tflite ahí (scp desde el PC)
```

```yaml
wakeword:
  provider: openwakeword
  model: /home/TU_USUARIO/asistente/models/oye_asistente.tflite
  threshold: 0.5
  framework: tflite
```

Reinicia y ajusta `threshold` desde la UI probando en voz alta.

---

## 8. Spotify (opcional)

Necesitas cuenta **Premium** y una app gratuita en
[developer.spotify.com](https://developer.spotify.com/dashboard):

1. *Create app* → Redirect URI `http://127.0.0.1:8974/callback`.
2. Obtén el refresh token (desde el PC, con navegador):
   ```bash
   .venv/bin/python scripts/spotify_auth.py --client-id XXX --client-secret YYY
   ```
   Copia las 3 líneas `SPOTIFY_*` que imprime a `~/asistente/.env` en la Pi.
3. En `config.yaml`, `skills.spotify.device_name` debe coincidir con el nombre del
   reproductor de la Pi.

### Reproductor en la Pi (spotifyd)

```bash
sudo apt install -y spotifyd          # o binario ARM de github.com/Spotifyd/spotifyd
# revisa systemd/spotifyd.conf (device_name, backend = pulseaudio)
sudo cp systemd/spotifyd.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now spotifyd
```

El asistente busca canciones con la Web API y manda la reproducción a ese dispositivo,
que saca el audio por el altavoz Bluetooth.

---

## Resolución de problemas

| Síntoma | Causa probable |
|---|---|
| `no se pudo contactar con Ollama/STT/TTS` | URL del PC mal, PC apagado, o cortafuegos. Prueba `curl http://IP_PC:8001/health` desde la Pi |
| No reacciona a la palabra de activación | `threshold` alto, micro flojo o mal `input_device`. Mira el nivel con `arecord -d3 test.wav && aplay test.wav` |
| Falsos disparos constantes | sube `wakeword.threshold` a 0.6–0.7 |
| Se oye entrecortado al hablar | coexistencia WiFi/BT (ver paso 6) |
| La UI no abre | el servicio no arrancó: `journalctl -u asistente -e` |
| `ALSA ... cannot open device` | falta `XDG_RUNTIME_DIR` correcto en el `.service`, o PipeWire del usuario no está activo (`systemctl --user status pipewire`) |
| Va muy lento | usa `qwen2.5:3b` y modelo Whisper `base`/`small` en el PC |

Logs en vivo: `journalctl -u asistente -f` o la sección **Logs** de la UI.
