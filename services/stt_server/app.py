"""STT server: envuelve faster-whisper en el contrato HTTP que espera el asistente.

  POST /transcribe?language=es   cuerpo = WAV (audio/wav)   -> {"text": "..."}
  GET  /health                                              -> {"ok": true}

Filtra alucinaciones de Whisper (texto inventado sobre silencio/ruido) por
probabilidad de "sin voz" y por log-prob medio.
"""

from __future__ import annotations

import io
import os
import re

from fastapi import FastAPI, Request
from faster_whisper import WhisperModel

MODEL = os.getenv("WHISPER_MODEL", "small")
COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
NO_SPEECH_MAX = float(os.getenv("WHISPER_NO_SPEECH_MAX", "0.6"))
LOGPROB_MIN = float(os.getenv("WHISPER_LOGPROB_MIN", "-1.0"))

app = FastAPI(title="stt_server")
_model = WhisperModel(MODEL, device=DEVICE, compute_type=COMPUTE)

# Frases típicas que Whisper inventa cuando no hay voz.
_HALLUCINATIONS = re.compile(
    r"^(gracias por ver el video\.?|subt[íi]tulos?.*|thanks for watching\.?|"
    r"[¡!]*\s*sonr[íi]e\s*[!]*|\.|www\..*|amara\.org.*)$",
    re.IGNORECASE,
)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "model": MODEL}


@app.post("/transcribe")
async def transcribe(request: Request, language: str = "es") -> dict:
    audio = await request.body()
    segments, _info = _model.transcribe(
        io.BytesIO(audio),
        language=language,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 400},
        condition_on_previous_text=False,
        no_speech_threshold=0.5,
        temperature=0.0,
    )

    parts: list[str] = []
    for seg in segments:
        if getattr(seg, "no_speech_prob", 0.0) > NO_SPEECH_MAX:
            continue
        if getattr(seg, "avg_logprob", 0.0) < LOGPROB_MIN:
            continue
        parts.append(seg.text)

    text = "".join(parts).strip()
    if _HALLUCINATIONS.match(text):
        text = ""
    return {"text": text}
