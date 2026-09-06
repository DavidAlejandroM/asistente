"""Dobles de prueba para cada interfaz. Permiten correr el bucle completo sin
hardware ni red (tests, modo demo, y tests de la UI de administración).
"""

from __future__ import annotations

from typing import Iterator

from asistente.llm.base import LLMResponse, Message, ToolSpec


class FakeAudioSource:
    """Emite una lista fija de frames y luego se detiene (StopIteration)."""

    def __init__(self, frames: list[bytes]):
        self._frames = list(frames)
        self.closed = False

    def frames(self) -> Iterator[bytes]:
        yield from self._frames

    def close(self) -> None:
        self.closed = True


class FakeAudioSink:
    def __init__(self) -> None:
        self.played: list[tuple[bytes, int]] = []

    def play(self, pcm: bytes, sample_rate: int) -> None:
        self.played.append((pcm, sample_rate))


class FakeWakeWord:
    """Se dispara cuando ve un frame igual a ``trigger``."""

    def __init__(self, trigger: bytes = b"WAKE"):
        self._trigger = trigger
        self.resets = 0

    def detect(self, frame: bytes) -> bool:
        return frame == self._trigger

    def reset(self) -> None:
        self.resets += 1


class FakeRecorder:
    """Ignora el audio real y devuelve un blob fijo; consume ``consume`` frames."""

    def __init__(self, audio: bytes = b"AUDIO", consume: int = 1):
        self._audio = audio
        self._consume = consume

    def record(self, frames: Iterator[bytes]) -> bytes:
        for _ in range(self._consume):
            next(frames, None)
        return self._audio


class FakeSTT:
    def __init__(self, transcript: str | list[str] = "hola asistente"):
        self._queue = [transcript] if isinstance(transcript, str) else list(transcript)

    def transcribe(self, audio: bytes, sample_rate: int) -> str:
        if not self._queue:
            return ""
        return self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]


class FakeTTS:
    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.spoken: list[str] = []

    def synthesize(self, text: str) -> tuple[bytes, int]:
        self.spoken.append(text)
        return (text.encode("utf-8"), self.sample_rate)


class ScriptedLLM:
    """Devuelve respuestas de una cola. Registra cada llamada."""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self.calls: list[tuple[list[Message], list[ToolSpec]]] = []

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        self.calls.append((list(messages), list(tools)))
        if len(self._responses) > 1:
            return self._responses.pop(0)
        return self._responses[0]


class EchoLLM:
    """Responde con el último mensaje de usuario, sin tools. Útil para humo."""

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"), ""
        )
        return LLMResponse(text=f"has dicho: {last_user}")
