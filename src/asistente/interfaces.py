"""Las interfaces "Lego". Cada pieza del asistente implementa una de estas.

Se usan ``typing.Protocol`` (tipado estructural): un adaptador no necesita heredar
de nada, solo tener los métodos correctos.
"""

from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

from asistente.llm.base import LLMResponse, Message, ToolSpec

# Formato de audio en todo el sistema: PCM 16-bit little-endian, mono.
# El sample rate va aparte (config.sample_rate, normalmente 16000).

FrameBytes = bytes  # un frame corto (p. ej. 20 ms) de PCM s16le mono


@runtime_checkable
class AudioSource(Protocol):
    def frames(self) -> Iterator[FrameBytes]:
        """Itera frames de audio del micrófono en tiempo real, indefinidamente."""
        ...

    def close(self) -> None: ...


@runtime_checkable
class AudioSink(Protocol):
    def play(self, pcm: bytes, sample_rate: int) -> None:
        """Reproduce PCM s16le mono y bloquea hasta terminar."""
        ...


@runtime_checkable
class WakeWord(Protocol):
    def detect(self, frame: FrameBytes) -> bool:
        """True si el frame completa la palabra de activación."""
        ...

    def reset(self) -> None: ...


@runtime_checkable
class Recorder(Protocol):
    def record(self, frames: Iterator[FrameBytes]) -> bytes:
        """Consume frames hasta detectar fin de habla (silencio) o timeout.

        Devuelve todo el PCM de la locución.
        """
        ...


@runtime_checkable
class STT(Protocol):
    def transcribe(self, audio: bytes, sample_rate: int) -> str: ...


@runtime_checkable
class TTS(Protocol):
    def synthesize(self, text: str) -> tuple[bytes, int]:
        """Devuelve ``(pcm_s16le_mono, sample_rate)``."""
        ...


@runtime_checkable
class LLM(Protocol):
    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse: ...
