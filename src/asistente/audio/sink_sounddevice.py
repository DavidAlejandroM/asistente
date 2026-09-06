"""Salida de audio (altavoz, incluido Bluetooth) vía ``sounddevice``."""

from __future__ import annotations

import logging

from asistente.audio.source_sounddevice import _resolve_device

log = logging.getLogger(__name__)


class SoundDeviceSink:
    def __init__(self, device: str | int | None = None, sd=None) -> None:
        if sd is None:  # pragma: no cover - requiere hardware
            import sounddevice as sd
        self._sd = sd
        self._device = _resolve_device(device, "output")

    def play(self, pcm: bytes, sample_rate: int) -> None:
        import numpy as np

        data = np.frombuffer(pcm, dtype=np.int16)
        try:
            self._sd.play(data, samplerate=sample_rate, device=self._device)
            self._sd.wait()
        except Exception as exc:  # noqa: BLE001
            log.warning("no se pudo reproducir audio: %s", exc)
