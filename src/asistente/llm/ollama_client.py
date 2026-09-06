"""Adaptador LLM para Ollama (``/api/chat`` con tools).

Traduce entre los tipos neutros (``asistente.llm.base``) y el formato de Ollama.
"""

from __future__ import annotations

import json

import httpx

from asistente.llm.base import LLMResponse, Message, ToolCall, ToolSpec


class OllamaClient:
    def __init__(self, url: str, model: str, timeout: float = 120.0) -> None:
        self._url = url.rstrip("/")
        self._model = model
        self._client = httpx.Client(timeout=timeout)

    def chat(self, messages: list[Message], tools: list[ToolSpec]) -> LLMResponse:
        payload: dict = {
            "model": self._model,
            "stream": False,
            "messages": [_to_ollama(m) for m in messages],
        }
        if tools:
            payload["tools"] = [_tool_to_ollama(t) for t in tools]

        try:
            r = self._client.post(f"{self._url}/api/chat", json=payload)
            r.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama respondió {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"No se pudo contactar con Ollama: {exc}") from exc

        message = r.json().get("message", {}) or {}
        text = message.get("content", "") or ""
        tool_calls = [
            ToolCall(
                id=f"call_{i}_{tc.get('function', {}).get('name', '')}",
                name=tc["function"]["name"],
                arguments=_parse_args(tc["function"].get("arguments", {})),
            )
            for i, tc in enumerate(message.get("tool_calls", []) or [])
        ]
        return LLMResponse(text=text, tool_calls=tool_calls)


def _parse_args(raw) -> dict:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return dict(raw or {})


def _to_ollama(m: Message) -> dict:
    out: dict = {"role": m.role, "content": m.content}
    if m.tool_calls:
        out["tool_calls"] = [
            {"function": {"name": tc.name, "arguments": tc.arguments}} for tc in m.tool_calls
        ]
    if m.role == "tool" and m.name:
        # sin tool_name, qwen2.5/llama a veces repiten la misma llamada en bucle
        out["tool_name"] = m.name
    return out


def _tool_to_ollama(t: ToolSpec) -> dict:
    return {
        "type": "function",
        "function": {
            "name": t.name,
            "description": t.description,
            "parameters": t.parameters,
        },
    }
