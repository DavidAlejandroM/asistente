"""Fuente de audio del micrófono vía ``sounddevice`` (PortAudio)."""

from __future__ import annotations

import logging
import queue
from typing import Iterator

log = logging.getLogger(__name__)


class SoundDeviceSource:
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 20,
        device: str | int | None = None,
        sd=None,
    ) -> None:
        if sd is None:  # pragma: no cover - requiere hardware
            import sounddevice as sd
        self._sd = sd
        self._blocksize = int(sample_rate * frame_ms / 1000)
        self._q: queue.Queue[bytes] = queue.Queue()
        self._stream = sd.RawInputStream(
            samplerate=sample_rate,
            blocksize=self._blocksize,
            dtype="int16",
            channels=1,
            device=device,
            callback=self._callback,
        )
        self._started = False

    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            log.debug("estado del micrófono: %s", status)
        self._q.put(bytes(indata))

    def frames(self) -> Iterator[bytes]:
        if not self._started:
            self._stream.start()
            self._started = True
        while True:
            yield self._q.get()

    def close(self) -> None:
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:  # noqa: BLE001
            pass
