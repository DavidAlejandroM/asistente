"""TTS server: envuelve Piper en el contrato HTTP que espera el asistente.

  POST /speak   {"text": "...", "voice": "es_ES-sharvard-medium"}   -> WAV
  GET  /health                                                     -> {"ok": true}
"""

from __future__ import annotations

import io
import os
import wave
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from piper import PiperVoice
from pydantic import BaseModel

from voices import ensure_voice

VOICES_DIR = Path(os.getenv("PIPER_VOICES_DIR", "/voices"))
DEFAULT_VOICE = os.getenv("PIPER_VOICE", "es_ES-sharvard-medium")

app = FastAPI(title="tts_server")
_cache: dict[str, PiperVoice] = {}


class SpeakIn(BaseModel):
    text: str
    voice: str | None = None


def _get_voice(name: str) -> PiperVoice:
    if name not in _cache:
        onnx = ensure_voice(name, VOICES_DIR)
        _cache[name] = PiperVoice.load(str(onnx), config_path=str(onnx) + ".json")
    return _cache[name]


def _synthesize_to_wav(voice: PiperVoice, text: str) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        if hasattr(voice, "synthesize_wav"):  # piper-tts >= 1.3
            voice.synthesize_wav(text, wav_file)
        else:  # piper-tts 1.2.x
            voice.synthesize(text, wav_file)
    return buf.getvalue()


@app.on_event("startup")
def _warmup() -> None:
    _get_voice(DEFAULT_VOICE)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "default_voice": DEFAULT_VOICE}


@app.post("/speak")
def speak(body: SpeakIn) -> Response:
    voice = _get_voice(body.voice or DEFAULT_VOICE)
    return Response(content=_synthesize_to_wav(voice, body.text), media_type="audio/wav")
