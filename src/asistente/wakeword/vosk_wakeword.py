"""Palabra de activación con Vosk (reconocimiento offline).

Ventaja sobre openWakeWord: la frase la eliges tú ("hey paco", "oye casa", …) sin
entrenar nada. Coste: más CPU (en una Pi Zero 2 W va justo; en un PC sobra).

El modelo se descarga solo la primera vez (~40 MB para español) a ~/.cache/vosk.
"""

from __future__ import annotations

import json
import logging

log = logging.getLogger(__name__)


class VoskWakeWord:
    def __init__(
        self,
        phrases: list[str],
        model_path: str | None = None,
        language: str = "es",
        sample_rate: int = 16000,
        cooldown_frames: int = 40,
        recognizer=None,
    ) -> None:
        self._phrases = [p.lower().strip() for p in phrases if p.strip()]
        self._cooldown_frames = cooldown_frames
        self._cooldown = 0

        if recognizer is None:
            from vosk import KaldiRecognizer, Model, SetLogLevel

            SetLogLevel(-1)
            model = Model(model_path) if model_path else Model(lang=language)
            grammar = json.dumps(self._phrases + ["[unk]"])
            recognizer = KaldiRecognizer(model, sample_rate, grammar)
        self._rec = recognizer

    def detect(self, frame: bytes) -> bool:
        if self._cooldown > 0:
            self._cooldown -= 1
            return False

        if self._rec.AcceptWaveform(frame):
            text = json.loads(self._rec.Result()).get("text", "")
            hit = self._matches(text)
        else:
            partial = json.loads(self._rec.PartialResult()).get("partial", "")
            hit = self._matches(partial)
            if hit:
                self._rec.Reset()  # evita re-disparar con el resultado final

        if hit:
            log.info("palabra de activación detectada (vosk)")
            self._cooldown = self._cooldown_frames
            return True
        return False

    def _matches(self, text: str) -> bool:
        text = (text or "").lower()
        return bool(text) and any(p in text for p in self._phrases)

    def reset(self) -> None:
        self._cooldown = 0
        self._rec.Reset()
