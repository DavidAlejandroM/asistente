"""Tipos neutros para hablar con cualquier LLM (estilo function-calling de OpenAI).

Cada adaptador concreto (Ollama, Claude, OpenAI...) traduce entre su formato y estos
tipos, de modo que el resto del sistema no depende de ningún proveedor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None  # solo para role == "tool"
    name: str | None = None  # nombre de la tool (role == "tool")


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema de los argumentos


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
