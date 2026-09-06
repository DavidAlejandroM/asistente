import httpx
import respx

from asistente.skills.home_assistant import HomeAssistantSkill

HA = "http://ha:8123"

_STATES = [
    {"entity_id": "light.cocina", "state": "off",
     "attributes": {"friendly_name": "Luz de la cocina"}},
    {"entity_id": "light.salon", "state": "on",
     "attributes": {"friendly_name": "Salón"}},
    {"entity_id": "switch.cafetera", "state": "off",
     "attributes": {"friendly_name": "Cafetera"}},
    {"entity_id": "sensor.temperatura", "state": "21",
     "attributes": {"friendly_name": "Temperatura"}},  # se ignora (no controlable)
]


def _skill():
    return HomeAssistantSkill(url=HA, token="tok")


@respx.mock
def test_enciende_por_nombre_amigable():
    respx.get(f"{HA}/api/states").mock(return_value=httpx.Response(200, json=_STATES))
    svc = respx.post(f"{HA}/api/services/light/turn_on").mock(
        return_value=httpx.Response(200, json=[])
    )

    out = _skill().run({"action": "on", "target": "luz de la cocina"})

    assert svc.called
    body = svc.calls.last.request.read().decode()
    assert "light.cocina" in body
    assert "cocina" in out.lower()
    assert svc.calls.last.request.headers["authorization"] == "Bearer tok"


@respx.mock
def test_toggle_usa_el_dominio_correcto():
    respx.get(f"{HA}/api/states").mock(return_value=httpx.Response(200, json=_STATES))
    svc = respx.post(f"{HA}/api/services/switch/toggle").mock(
        return_value=httpx.Response(200, json=[])
    )

    _skill().run({"action": "toggle", "target": "cafetera"})

    assert svc.called


@respx.mock
def test_target_desconocido_no_llama_a_ningun_servicio():
    respx.get(f"{HA}/api/states").mock(return_value=httpx.Response(200, json=_STATES))
    out = _skill().run({"action": "on", "target": "garaje"})
    assert "no" in out.lower()


@respx.mock
def test_list_devices_solo_dispositivos_controlables():
    respx.get(f"{HA}/api/states").mock(return_value=httpx.Response(200, json=_STATES))
    out = _skill().run({"action": "list"})
    assert "cocina" in out.lower() and "salón" in out.lower()
    assert "temperatura" not in out.lower()


@respx.mock
def test_ha_caido_devuelve_mensaje_amable():
    respx.get(f"{HA}/api/states").mock(side_effect=httpx.ConnectError("x"))
    out = _skill().run({"action": "on", "target": "cocina"})
    assert "no" in out.lower()
