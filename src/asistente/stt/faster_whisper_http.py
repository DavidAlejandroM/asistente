"""Cliente STT contra el servicio ``stt_server`` del PC (faster-whisper).

Contrato: ``POST /transcribe?language=<lang>`` con cuerpo = WAV (audio/wav),
respuesta JSON ``{"text": "..."}``.
"""

from __future__ import annotations

import httpx

from asistente.audio.wavutil import pcm_to_wav


class FasterWhisperHTTP:
    def __init__(self, url: str, language: str = "es", timeout: float = 60.0) -> None:
        self._url = url.rstrip("/")
        self._language = language
        self._client = httpx.Client(timeout=timeout)

    def transcribe(self, audio: bytes, sample_rate: int) -> str:
        wav = pcm_to_wav(audio, sample_rate=sample_rate)
        try:
            r = self._client.post(
                f"{self._url}/transcribe",
                params={"language": self._language},
                content=wav,
                headers={"content-type": "audio/wav"},
            )
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"STT respondió {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"No se pudo contactar con el STT: {exc}") from exc

        return (r.json().get("text") or "").strip()
