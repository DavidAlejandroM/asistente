"""El orquestador: une audio ↔ wake word ↔ STT ↔ cerebro ↔ TTS ↔ altavoz.

Mantiene un ``Status`` observable para la UI de administración.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Iterator

log = logging.getLogger(__name__)

_NO_ENTENDI = "Perdona, no te he entendido."


class State(str, enum.Enum):
    IDLE = "idle"
    WAITING_WAKE = "waiting_wake"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class Status:
    state: State = State.IDLE
    last_transcript: str = ""
    last_response: str = ""
    last_error: str = ""
    updated_at: float = field(default_factory=time.time)


class Orchestrator:
    def __init__(
        self,
        *,
        audio_source,
        wakeword,
        recorder,
        stt,
        brain,
        tts,
        sink,
        sample_rate: int = 16000,
        wake_response: str = "",
        no_understand_message: str = _NO_ENTENDI,
    ) -> None:
        self._source = audio_source
        self._wakeword = wakeword
        self._recorder = recorder
        self._stt = stt
        self._brain = brain
        self._tts = tts
        self._sink = sink
        self._sample_rate = sample_rate
        self._wake_response = wake_response
        self._no_understand = no_understand_message

        self._status = Status()
        self._lock = threading.Lock()
        self._audio_lock = threading.Lock()
        self._stop = threading.Event()
        self._frames: Iterator[bytes] | None = None

    # -- observabilidad para la UI --------------------------------------------
    @property
    def brain(self):
        return self._brain

    @property
    def skills(self):
        return self._brain.skills

    def status(self) -> Status:
        with self._lock:
            return Status(
                state=self._status.state,
                last_transcript=self._status.last_transcript,
                last_response=self._status.last_response,
                last_error=self._status.last_error,
                updated_at=self._status.updated_at,
            )

    def _set(self, **kw) -> None:
        with self._lock:
            for k, v in kw.items():
                setattr(self._status, k, v)
            self._status.updated_at = time.time()

    # -- bucle ---------------------------------------------------------------
    def _ensure_frames(self) -> Iterator[bytes]:
        if self._frames is None:
            self._frames = iter(self._source.frames())
        return self._frames

    def run_once(self) -> bool:
        """Espera una activación y atiende una petición. False si el audio se agota."""
        frames = self._ensure_frames()
        self._set(state=State.WAITING_WAKE)
        self._wakeword.reset()

        for frame in frames:
            if self._wakeword.detect(frame):
                break
        else:
            self._set(state=State.IDLE)
            return False

        try:
            if self._wake_response:
                self._speak(self._wake_response)

            self._set(state=State.LISTENING)
            audio = self._recorder.record(frames)

            self._set(state=State.THINKING)
            transcript = self._stt.transcribe(audio, self._sample_rate).strip()
            self._set(last_transcript=transcript)

            if not transcript:
                self._speak(self._no_understand)
                self._set(state=State.IDLE)
                return True

            response = self._brain.process(transcript)
            self._set(last_response=response)

            self._speak(response)
            self._set(state=State.IDLE)
            return True
        except Exception as exc:  # noqa: BLE001 - no queremos que un fallo tumbe el servicio
            log.exception("error atendiendo la petición")
            self._set(state=State.ERROR, last_error=str(exc))
            return True

    def run_forever(self) -> None:
        self._stop.clear()
        while not self._stop.is_set():
            if self.run_once() is False:
                break

    def stop(self) -> None:
        self._stop.set()

    def announce(self, text: str) -> None:
        """Dice algo de forma proactiva (p. ej. una alarma). Seguro entre hilos."""
        self._speak(text)

    def _speak(self, text: str) -> None:
        with self._audio_lock:
            prev = self._status.state
            self._set(state=State.SPEAKING)
            pcm, sr = self._tts.synthesize(text)
            self._sink.play(pcm, sr)
            self._set(state=prev)
