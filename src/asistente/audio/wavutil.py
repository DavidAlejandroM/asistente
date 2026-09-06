"""Conversión PCM s16le mono ↔ contenedor WAV, sin dependencias externas."""

from __future__ import annotations

import io
import wave


def pcm_to_wav(pcm: bytes, sample_rate: int, channels: int = 1, sampwidth: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_to_pcm(data: bytes) -> tuple[bytes, int]:
    with wave.open(io.BytesIO(data), "rb") as w:
        rate = w.getframerate()
        pcm = w.readframes(w.getnframes())
    return pcm, rate
