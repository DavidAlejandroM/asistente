"""Cliente TTS contra el servicio ``tts_server`` del PC (Piper).

Contrato: ``POST /speak`` con JSON ``{"text": ..., "voice": ...}``, respuesta = WAV.
"""

from __future__ import annotations

import httpx

from asistente.audio.wavutil import wav_to_pcm


class PiperHTTP:
    def __init__(self, url: str, voice: str, timeout: float = 60.0) -> None:
        self._url = url.rstrip("/")
        self._voice = voice
        self._client = httpx.Client(timeout=timeout)

    def synthesize(self, text: str) -> tuple[bytes, int]:
        try:
            r = self._client.post(
                f"{self._url}/speak", json={"text": text, "voice": self._voice}
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"TTS respondió {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"No se pudo contactar con el TTS: {exc}") from exc

        return wav_to_pcm(r.content)
