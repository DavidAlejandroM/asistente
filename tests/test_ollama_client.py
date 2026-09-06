import httpx
import pytest
import respx

from asistente.llm.base import Message, ToolCall, ToolSpec
from asistente.llm.ollama_client import OllamaClient

URL = "http://pc:11434"


@respx.mock
def test_devuelve_texto_plano():
    respx.post(f"{URL}/api/chat").mock(
        return_value=httpx.Response(
            200, json={"message": {"role": "assistant", "content": "son las tres"}}
        )
    )
    client = OllamaClient(url=URL, model="qwen2.5:7b")

    resp = client.chat([Message(role="user", content="qué hora es")], [])

    assert resp.text == "son las tres"
    assert resp.tool_calls == []


@respx.mock
def test_traduce_tool_calls_de_ollama():
    route = respx.post(f"{URL}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "get_weather", "arguments": {"when": "hoy"}}}
                    ],
                }
            },
        )
    )
    client = OllamaClient(url=URL, model="m")
    tools = [ToolSpec(name="get_weather", description="tiempo", parameters={"type": "object"})]

    resp = client.chat([Message(role="user", content="tiempo?")], tools)

    assert len(resp.tool_calls) == 1
    tc = resp.tool_calls[0]
    assert tc.name == "get_weather" and tc.arguments == {"when": "hoy"}
    assert tc.id  # se genera un id estable

    sent = route.calls.last.request
    body = sent.read().decode()
    assert '"tools"' in body and "get_weather" in body


@respx.mock
def test_serializa_historial_con_roles_y_resultados_de_tool():
    route = respx.post(f"{URL}/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": "ok"}})
    )
    client = OllamaClient(url=URL, model="m")
    history = [
        Message(role="user", content="pon la luz"),
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="1", name="luz", arguments={"x": 1})],
        ),
        Message(role="tool", content="luz encendida", tool_call_id="1", name="luz"),
    ]

    client.chat(history, [])

    import json

    payload = json.loads(route.calls.last.request.read())
    roles = [m["role"] for m in payload["messages"]]
    assert roles == ["user", "assistant", "tool"]
    assert payload["messages"][1]["tool_calls"][0]["function"]["name"] == "luz"
    assert payload["messages"][2]["content"] == "luz encendida"
    assert payload["messages"][2]["tool_name"] == "luz"  # evita bucles de tool-calling
    assert payload["stream"] is False


@respx.mock
def test_error_http_se_convierte_en_excepcion_clara():
    respx.post(f"{URL}/api/chat").mock(return_value=httpx.Response(500, text="boom"))
    client = OllamaClient(url=URL, model="m")

    with pytest.raises(RuntimeError, match="Ollama"):
        client.chat([Message(role="user", content="hola")], [])
