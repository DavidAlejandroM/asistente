import textwrap

from asistente.brain import Brain
from asistente.config import load_config
from asistente.factory import build_brain, build_orchestrator, register_llm
from asistente.llm.base import LLMResponse
from asistente.orchestrator import Orchestrator


def _cfg(tmp_path, extra=""):
    p = tmp_path / "config.yaml"
    p.write_text(
        textwrap.dedent(
            """
            llm: {provider: fake}
            stt: {provider: fake}
            tts: {provider: fake}
            wakeword: {provider: fake}
            audio: {source: fake, sink: fake, recorder: fake}
            """
        )
        + textwrap.dedent(extra)
    )
    return load_config(p)


def test_build_brain_usa_el_proveedor_de_la_config(tmp_path):
    brain = build_brain(_cfg(tmp_path))
    assert isinstance(brain, Brain)
    # el proveedor fake responde por eco
    assert "hola" in brain.process("hola")


def test_build_orchestrator_monta_el_pipeline_completo(tmp_path):
    orch = build_orchestrator(_cfg(tmp_path))
    assert isinstance(orch, Orchestrator)


def test_se_pueden_registrar_proveedores_nuevos(tmp_path):
    register_llm("mi_llm", lambda settings: _Canned())
    cfg = _cfg(tmp_path, "llm: {provider: mi_llm}\n")
    brain = build_brain(cfg)
    assert brain.process("x") == "respuesta fija"


class _Canned:
    def chat(self, messages, tools):
        return LLMResponse(text="respuesta fija")
