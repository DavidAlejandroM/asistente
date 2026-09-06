import textwrap

from fastapi.testclient import TestClient

from asistente.admin.server import create_app
from asistente.orchestrator import State, Status
from asistente.skills.registry import SkillRegistry
from asistente.skills.timers import TimerService, TimerSkill


class FakeSkill:
    def __init__(self, name):
        self.name = name
        self.description = f"skill {name}"
        self.parameters = {"type": "object", "properties": {}}

    def run(self, args):
        return "ok"


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class FakeOrchestrator:
    def __init__(self, registry):
        self._registry = registry
        self.announced = []
        self._status = Status(
            state=State.IDLE, last_transcript="qué hora es", last_response="las tres"
        )

    def status(self):
        return self._status

    def announce(self, text):
        self.announced.append(text)

    @property
    def skills(self):
        return self._registry


def _client(tmp_path):
    reg = SkillRegistry()
    reg.register(FakeSkill("get_weather"))
    clock = FakeClock()
    reg.register(TimerSkill(TimerService(on_expire=lambda t: None, clock=clock), clock=clock))
    orch = FakeOrchestrator(reg)

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        textwrap.dedent(
            """
            llm: {provider: fake}
            stt: {provider: fake}
            tts: {provider: fake}
            wakeword: {provider: fake}
            """
        )
    )
    app = create_app(orchestrator=orch, cfg_path=cfg_path)
    return TestClient(app), orch, reg


def test_dashboard_muestra_estado_y_skills(tmp_path):
    client, *_ = _client(tmp_path)
    r = client.get("/")
    assert r.status_code == 200
    assert "qué hora es" in r.text
    assert "get_weather" in r.text


def test_api_status_json(tmp_path):
    client, *_ = _client(tmp_path)
    r = client.get("/api/status")
    assert r.json()["state"] == "idle"
    assert r.json()["last_response"] == "las tres"


def test_toggle_skill(tmp_path):
    client, orch, reg = _client(tmp_path)
    assert reg.is_enabled("get_weather")

    r = client.post("/api/skills/get_weather/toggle")
    assert r.status_code == 200
    assert not reg.is_enabled("get_weather")

    client.post("/api/skills/get_weather/toggle")
    assert reg.is_enabled("get_weather")


def test_crear_y_cancelar_temporizador(tmp_path):
    client, *_ = _client(tmp_path)
    r = client.post("/api/timers", data={"seconds": "120", "label": "té"})
    assert r.status_code == 200

    listing = client.get("/api/timers").json()
    assert len(listing) == 1 and listing[0]["label"] == "té"
    tid = listing[0]["id"]

    client.post(f"/api/timers/{tid}/cancel")
    assert client.get("/api/timers").json() == []


def test_probar_altavoz_llama_announce(tmp_path):
    client, orch, _ = _client(tmp_path)
    client.post("/api/test-audio")
    assert orch.announced


def test_guardar_config_invalida_da_400_y_no_escribe(tmp_path):
    client, *_ = _client(tmp_path)
    original = (tmp_path / "config.yaml").read_text()

    r = client.post("/api/config", data={"yaml": "llm: {provider: fake}\n:::bad"})
    assert r.status_code == 400
    assert (tmp_path / "config.yaml").read_text() == original


def test_guardar_config_valida_escribe_el_archivo(tmp_path):
    client, *_ = _client(tmp_path)
    nuevo = textwrap.dedent(
        """
        llm: {provider: ollama, url: "http://x:1", model: m}
        stt: {provider: fake}
        tts: {provider: fake}
        wakeword: {provider: fake}
        """
    )
    r = client.post("/api/config", data={"yaml": nuevo})
    assert r.status_code == 200
    assert "ollama" in (tmp_path / "config.yaml").read_text()


def test_logs_history(tmp_path):
    import logging

    client, *_ = _client(tmp_path)
    logging.getLogger("test").warning("mensaje de prueba")
    r = client.get("/api/logs")
    assert any("mensaje de prueba" in line for line in r.json())
