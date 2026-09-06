# Asistente de voz modular

Asistente de voz estilo Alexa para **Raspberry Pi Zero 2 W**. Arquitectura "Lego":
cada pieza (wake word, STT, LLM, TTS, skills, audio) está detrás de una interfaz y se
elige por configuración. Los modelos pesados (LLM/STT/TTS) corren en un PC de la red.

## Estado

| Paso | Descripción | Estado |
|---|---|---|
| 1 | Esqueleto: interfaces, config, cerebro, orquestador, factory, CLI, fakes | ✅ hecho |
| 2 | Servicios del PC (Ollama + faster-whisper HTTP + Piper HTTP) — `services/` | ✅ hecho |
| 3 | Adaptadores reales: OllamaClient, FasterWhisperHTTP, PiperHTTP | ✅ hecho |
| 4 | Audio + wake word en la Pi (sounddevice, openWakeWord, VAD) | ✅ hecho |
| 5 | Skills: clima (Open-Meteo), temporizadores/alarmas, Home Assistant, Spotify | ✅ hecho |
| 6 | Interfaz de administración web (FastAPI, `admin/`) — puerto 8080 | ✅ hecho |
| 7 | Infra Spotify/Bluetooth (`systemd/spotifyd*`, `bt-autoconnect`) | ✅ hecho |
| 8 | Empaquetado (`systemd/asistente.service`, `docs/raspberry-pi.md`) | ✅ hecho |

**Todo el código está listo.** Falta ejecutarlo en la Raspberry Pi real
(ver [docs/raspberry-pi.md](docs/raspberry-pi.md)) y, opcionalmente, dar credenciales
de Home Assistant y Spotify.

Ver el plan completo en `/home/alejandro/.claude/plans/quiero-crear-un-asistente-soft-grove.md`.

## Desarrollo

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest

# probar sin hardware ni servidores:
cp config.example.yaml config.yaml
.venv/bin/python -m asistente --fake --text      # teclado
.venv/bin/python -m asistente --fake --once      # un ciclo del pipeline
```

## Arquitectura

```
Pi Zero 2 W:  micro → wake word → grabador(VAD) → [STT] → cerebro(LLM+skills) → [TTS] → altavoz BT
PC:           Ollama + faster-whisper + Piper (HTTP en la LAN)
```

- `src/asistente/interfaces.py` — las interfaces Lego (Protocols).
- `src/asistente/brain.py` — bucle LLM ↔ tools, puro y testeable.
- `src/asistente/orchestrator.py` — pipeline de audio + estado para la UI.
- `src/asistente/factory.py` — construye todo desde `config.yaml`; registros de proveedores.
- `src/asistente/fakes/` — dobles para tests y modo `--fake`.
