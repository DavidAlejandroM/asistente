"""Grabador de locuciones con detección de actividad de voz (VAD).

``VadRecorder`` consume frames del micrófono desde que se activa el asistente y
devuelve el PCM de lo que dijo el usuario, cortando en el silencio final.

El VAD concreto se inyecta (``vad.is_speech(frame) -> bool``). El de producción
envuelve ``webrtcvad``; en tests se usa uno falso.
"""

from __future__ import annotations

import array
import logging
from collections import deque
from typing import Iterable, Iterator, Protocol

log = logging.getLogger(__name__)


def rms(pcm: bytes) -> float:
    """Nivel RMS de PCM s16le. ~0 en silencio, cientos-miles en voz."""
    if len(pcm) < 2:
        return 0.0
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    return (sum(x * x for x in a) / len(a)) ** 0.5


class _Vad(Protocol):
    def is_speech(self, frame: bytes) -> bool: ...


class WebrtcVad:
    """Envoltura de webrtcvad (frames de 10/20/30 ms, 8/16/32/48 kHz)."""

    def __init__(self, sample_rate: int = 16000, aggressiveness: int = 3) -> None:
        import webrtcvad

        self._vad = webrtcvad.Vad(aggressiveness)
        self._rate = sample_rate

    def is_speech(self, frame: bytes) -> bool:
        try:
            return self._vad.is_speech(frame, self._rate)
        except Exception:  # noqa: BLE001 - frame de tamaño raro al final
            return False


class VadRecorder:
    def __init__(
        self,
        vad: _Vad,
        *,
        sample_rate: int = 16000,
        frame_ms: int = 20,
        start_frames: int = 4,
        silence_ms: int = 700,
        preroll_ms: int = 200,
        max_duration_s: float = 12.0,
        max_wait_s: float = 6.0,
        min_utterance_ms: int = 350,
        min_rms: float = 180.0,
    ) -> None:
        self._vad = vad
        self._frame_ms = frame_ms
        self._frame_bytes = int(sample_rate * frame_ms / 1000) * 2
        self._start_frames = start_frames
        self._silence_frames = max(1, silence_ms // frame_ms)
        self._preroll_frames = max(0, preroll_ms // frame_ms)
        self._max_frames = max(1, int(max_duration_s * 1000) // frame_ms)
        self._max_wait_frames = max(1, int(max_wait_s * 1000) // frame_ms)
        self._min_utterance_frames = max(0, min_utterance_ms // frame_ms)
        self._min_rms = min_rms

    def record(self, frames: Iterable[bytes]) -> bytes:
        preroll: deque[bytes] = deque(maxlen=self._preroll_frames)
        pending: list[bytes] = []
        voiced: list[bytes] = []
        started = False
        speech_run = 0
        silence_run = 0
        waited = 0

        for frame in self._reframe(frames):
            speech = self._vad.is_speech(frame)

            if not started:
                waited += 1
                if speech:
                    pending.append(frame)
                    speech_run += 1
                    if speech_run >= self._start_frames:
                        started = True
                        voiced.extend(preroll)
                        voiced.extend(pending)
                        pending.clear()
                else:
                    preroll.append(frame)
                    for p in pending:
                        preroll.append(p)
                    pending.clear()
                    speech_run = 0
                if waited >= self._max_wait_frames:
                    return b""
                continue

            voiced.append(frame)
            if speech:
                silence_run = 0
            else:
                silence_run += 1
                if silence_run >= self._silence_frames:
                    break
            if len(voiced) >= self._max_frames:
                break

        # descarta ráfagas de ruido demasiado cortas para ser una frase
        voiced_frames = len(voiced) - self._preroll_frames
        if not started or voiced_frames < self._min_utterance_frames:
            return b""
        audio = b"".join(voiced)
        level = rms(audio)
        if level < self._min_rms:
            log.debug("locución descartada por nivel bajo (rms=%.0f)", level)
            return b""
        return audio

    def _reframe(self, frames: Iterable[bytes]) -> Iterator[bytes]:
        """Reagrupa chunks de tamaño arbitrario en frames exactos."""
        buf = bytearray()
        for chunk in frames:
            buf.extend(chunk)
            while len(buf) >= self._frame_bytes:
                yield bytes(buf[: self._frame_bytes])
                del buf[: self._frame_bytes]
