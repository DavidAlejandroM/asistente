from asistente.brain import Brain
from asistente.llm.base import LLMResponse, ToolCall, ToolSpec
from asistente.skills.registry import SkillRegistry


class ScriptedLLM:
    """LLM de prueba: devuelve respuestas de una lista, en orden."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append((list(messages), list(tools)))
        return self._responses.pop(0)


class RecordingSkill:
    name = "encender_luz"
    description = "Enciende una luz"
    parameters = {"type": "object", "properties": {"sala": {"type": "string"}}}

    def __init__(self):
        self.runs = []

    def run(self, args):
        self.runs.append(args)
        return f"luz de {args['sala']} encendida"


def test_devuelve_texto_del_llm_cuando_no_hay_tool_calls():
    llm = ScriptedLLM([LLMResponse(text="Hola, ¿qué tal?")])
    brain = Brain(llm=llm, skills=SkillRegistry(), system_prompt="eres un asistente")

    assert brain.process("hola") == "Hola, ¿qué tal?"


def test_ejecuta_skill_y_reconsulta_al_llm_con_el_resultado():
    skill = RecordingSkill()
    registry = SkillRegistry()
    registry.register(skill)
    llm = ScriptedLLM(
        [
            LLMResponse(text="", tool_calls=[ToolCall(id="1", name="encender_luz", arguments={"sala": "cocina"})]),
            LLMResponse(text="Listo, luz de la cocina encendida"),
        ]
    )
    brain = Brain(llm=llm, skills=registry, system_prompt="sys")

    result = brain.process("enciende la luz de la cocina")

    assert skill.runs == [{"sala": "cocina"}]
    assert result == "Listo, luz de la cocina encendida"
    # el segundo turno debe incluir el resultado de la tool en el historial
    second_turn_messages = llm.calls[1][0]
    assert any(m.role == "tool" and "cocina encendida" in m.content for m in second_turn_messages)


def test_expone_las_skills_como_tool_specs_al_llm():
    registry = SkillRegistry()
    registry.register(RecordingSkill())
    llm = ScriptedLLM([LLMResponse(text="ok")])
    brain = Brain(llm=llm, skills=registry, system_prompt="sys")

    brain.process("hola")

    tools = llm.calls[0][1]
    assert [t.name for t in tools] == ["encender_luz"]
    assert isinstance(tools[0], ToolSpec)


def test_corta_el_bucle_de_tools_tras_el_maximo_de_iteraciones():
    registry = SkillRegistry()
    registry.register(RecordingSkill())
    loop_response = LLMResponse(
        text="", tool_calls=[ToolCall(id="x", name="encender_luz", arguments={"sala": "cocina"})]
    )
    llm = ScriptedLLM([loop_response] * 10)
    brain = Brain(llm=llm, skills=registry, system_prompt="sys", max_tool_iterations=3)

    result = brain.process("bucle")

    assert len(llm.calls) == 3
    assert isinstance(result, str) and result != ""
