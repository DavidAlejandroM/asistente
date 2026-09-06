import textwrap

import httpx
import respx

from asistente.config import load_config
from asistente.factory import build_brain


@respx.mock
def test_build_brain_con_ollama_real_hace_una_peticion_http(tmp_path):
    respx.post("http://pc:11434/api/chat").mock(
        return_value=httpx.Response(200, json={"message": {"content": "hola"}})
    )
    p = tmp_path / "config.yaml"
    p.write_text(
        textwrap.dedent(
            """
            llm: {provider: ollama, url: "http://pc:11434", model: m}
            stt: {provider: faster_whisper_http, url: "http://pc:8001"}
            tts: {provider: piper_http, url: "http://pc:8002", voice: v}
            wakeword: {provider: fake}
            """
        )
    )
    brain = build_brain(load_config(p))

    assert brain.process("hey") == "hola"
