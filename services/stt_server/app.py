"""STT server: envuelve faster-whisper en el contrato HTTP que espera el asistente.

  POST /transcribe?language=es   cuerpo = WAV (audio/wav)   -> {"text": "..."}
  GET  /health                                              -> {"ok": true}
"""

from __future__ import annotations

import io
import os

from fastapi import FastAPI, Request
from faster_whisper import WhisperModel

MODEL = os.getenv("WHISPER_MODEL", "small")
COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")

app = FastAPI(title="stt_server")
_model = WhisperModel(MODEL, device=DEVICE, compute_type=COMPUTE)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "model": MODEL}


@app.post("/transcribe")
async def transcribe(request: Request, language: str = "es") -> dict:
    audio = await request.body()
    segments, _info = _model.transcribe(
        io.BytesIO(audio), language=language, vad_filter=True
    )
    text = "".join(seg.text for seg in segments).strip()
    return {"text": text}
