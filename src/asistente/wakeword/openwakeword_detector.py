"""Detector de palabra de activación con openWakeWord (ligero, corre en la Pi).

El modelo se inyecta para poder testear la lógica de umbral/cooldown sin cargar
tflite. En producción se crea un ``openwakeword.model.Model``.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class OpenWakeWordDetector:
    def __init__(
        self,
        model: str = "hey_jarvis",
        threshold: float = 0.5,
        cooldown_frames: int = 40,
        framework: str = "tflite",
        model_impl=None,
    ) -> None:
        # openWakeWord indexa los scores por el nombre del modelo sin extensión,
        # tanto si es uno incorporado ("hey_jarvis") como una ruta a un .tflite propio.
        self._key = Path(model).stem
        self._threshold = threshold
        self._cooldown_frames = cooldown_frames
        self._cooldown = 0
        if model_impl is None:
            model_impl = self._load(model, framework)
        self._model = model_impl

    @staticmethod
    def _load(model: str, framework: str):
        from openwakeword.model import Model

        try:  # descarga los modelos base la primera vez
            import openwakeword

            openwakeword.utils.download_models()
        except Exception:  # noqa: BLE001
            pass

        # La firma de Model cambió entre versiones de openWakeWord.
        for kwargs in (
            {"wakeword_models": [model], "inference_framework": framework},  # >= 0.5
            {"wakeword_models": [model]},
            {"wakeword_model_paths": [model]},                               # 0.4.x
        ):
            try:
                return Model(**kwargs)
            except TypeError:
                continue
        raise RuntimeError(
            "No se pudo inicializar openWakeWord; revisa la versión instalada."
        )

    def detect(self, frame: bytes) -> bool:
        if self._cooldown > 0:
            self._cooldown -= 1
            return False

        import numpy as np

        samples = np.frombuffer(frame, dtype=np.int16)
        scores = self._model.predict(samples)
        score = scores.get(self._key)
        if score is None:
            score = max(scores.values(), default=0.0)

        if score >= self._threshold:
            log.info("palabra de activación detectada (%.2f)", score)
            self._cooldown = self._cooldown_frames
            return True
        return False

    def reset(self) -> None:
        self._cooldown = 0
        reset = getattr(self._model, "reset", None)
        if callable(reset):
            reset()
