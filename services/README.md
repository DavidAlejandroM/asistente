# Servicios de IA (PC de escritorio)

Todo local y gratis. Requiere Docker + Docker Compose.

```bash
cd services
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:7b   # modelo con tool-calling y buen español
```

| Servicio | Puerto | Contrato |
|---|---|---|
| ollama | 11434 | API nativa de Ollama (`/api/chat`) |
| stt (faster-whisper) | 8001 | `POST /transcribe?language=es` cuerpo=WAV → `{"text": "..."}` |
| tts (Piper) | 8002 | `POST /speak {"text","voice"}` → WAV |

Comprobación rápida:

```bash
curl -s localhost:8001/health
curl -s localhost:8002/health
curl -s localhost:8002/speak -H 'content-type: application/json' \
  -d '{"text":"hola, esto es una prueba"}' -o /tmp/out.wav && aplay /tmp/out.wav
```

En `config.yaml` de la Pi, apunta las URLs a la IP del PC en la LAN:

```yaml
llm: {provider: ollama, url: "http://IP_DEL_PC:11434", model: qwen2.5:7b}
stt: {provider: faster_whisper_http, url: "http://IP_DEL_PC:8001", language: es}
tts: {provider: piper_http, url: "http://IP_DEL_PC:8002", voice: es_ES-sharvard-medium}
```
