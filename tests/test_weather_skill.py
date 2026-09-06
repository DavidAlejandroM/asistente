import httpx
import respx

from asistente.config import LocationConfig
from asistente.skills.weather import WeatherSkill

API = "https://api.open-meteo.com/v1/forecast"

_FORECAST = {
    "current": {"temperature_2m": 21.3, "weather_code": 61, "relative_humidity_2m": 80},
    "daily": {
        "time": ["2026-09-06", "2026-09-07", "2026-09-08"],
        "weather_code": [63, 2, 0],
        "temperature_2m_max": [24.0, 25.1, 26.0],
        "temperature_2m_min": [13.0, 12.5, 12.0],
        "precipitation_probability_max": [90, 40, 10],
    },
}


def _skill():
    return WeatherSkill(
        LocationConfig(lat=6.28, lon=-75.33, name="San Vicente", timezone="America/Bogota")
    )


@respx.mock
def test_tiempo_actual_menciona_temperatura_y_estado():
    route = respx.get(API).mock(return_value=httpx.Response(200, json=_FORECAST))

    out = _skill().run({"when": "ahora"})

    assert "21" in out
    assert "lluvia" in out.lower()
    params = route.calls.last.request.url.params
    assert params["latitude"] == "6.28"
    assert params["timezone"] == "America/Bogota"


@respx.mock
def test_tiempo_manana_usa_el_segundo_dia_del_pronostico():
    respx.get(API).mock(return_value=httpx.Response(200, json=_FORECAST))

    out = _skill().run({"when": "mañana"})

    assert "25" in out and "12" in out  # max y min del día 2


@respx.mock
def test_when_desconocido_cae_en_hoy():
    respx.get(API).mock(return_value=httpx.Response(200, json=_FORECAST))
    out = _skill().run({"when": "cualquier cosa"})
    assert "24" in out


@respx.mock
def test_error_de_api_devuelve_texto_amable_no_excepcion():
    respx.get(API).mock(return_value=httpx.Response(500))
    out = _skill().run({"when": "ahora"})
    assert "no" in out.lower() and "tiempo" in out.lower()


def test_metadata_de_la_skill():
    s = _skill()
    assert s.name == "get_weather"
    assert "when" in s.parameters["properties"]
