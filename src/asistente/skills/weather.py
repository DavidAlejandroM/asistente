"""Skill del tiempo con Open-Meteo (gratis, sin clave, sin cuenta)."""

from __future__ import annotations

import logging

import httpx

from asistente.config import LocationConfig

log = logging.getLogger(__name__)

_API = "https://api.open-meteo.com/v1/forecast"

# Códigos WMO -> descripción corta en español
_WMO = {
    0: "despejado",
    1: "casi despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "niebla",
    48: "niebla con escarcha",
    51: "llovizna ligera",
    53: "llovizna",
    55: "llovizna intensa",
    61: "lluvia ligera",
    63: "lluvia",
    65: "lluvia fuerte",
    71: "nieve ligera",
    73: "nieve",
    75: "nieve intensa",
    80: "chubascos",
    81: "chubascos",
    82: "chubascos fuertes",
    95: "tormenta",
    96: "tormenta con granizo",
    99: "tormenta fuerte con granizo",
}


def _describe(code: int) -> str:
    return _WMO.get(int(code), "condiciones variables")


class WeatherSkill:
    name = "get_weather"
    description = (
        "Consulta el tiempo/clima real para la ubicación configurada. "
        "Úsala siempre que pregunten por el tiempo; no lo inventes."
    )
    parameters = {
        "type": "object",
        "properties": {
            "when": {
                "type": "string",
                "enum": ["ahora", "hoy", "mañana"],
                "description": "momento consultado",
            }
        },
        "required": ["when"],
    }

    def __init__(self, location: LocationConfig, timeout: float = 15.0) -> None:
        self._loc = location
        self._client = httpx.Client(timeout=timeout)

    def run(self, args: dict) -> str:
        when = str(args.get("when", "hoy")).lower()
        try:
            data = self._fetch()
        except Exception as exc:  # noqa: BLE001
            log.warning("Open-Meteo falló: %s", exc)
            return "Ahora mismo no puedo consultar el tiempo."

        place = self._loc.name or "tu zona"
        if when == "ahora":
            cur = data.get("current", {})
            temp = round(cur.get("temperature_2m", 0))
            hum = cur.get("relative_humidity_2m")
            estado = _describe(cur.get("weather_code", -1))
            extra = f", humedad {round(hum)}%" if hum is not None else ""
            return f"En {place} ahora hay {temp} grados y {estado}{extra}."

        idx = 1 if when.startswith("mañana") else 0
        daily = data.get("daily", {})
        try:
            tmax = round(daily["temperature_2m_max"][idx])
            tmin = round(daily["temperature_2m_min"][idx])
            estado = _describe(daily["weather_code"][idx])
            prob = daily.get("precipitation_probability_max", [None] * (idx + 1))[idx]
        except (KeyError, IndexError):
            return "No tengo el pronóstico para ese día."

        cuando = "mañana" if idx == 1 else "hoy"
        lluvia = f" Probabilidad de lluvia {prob}%." if prob is not None else ""
        return f"{cuando.capitalize()} en {place}: {estado}, entre {tmin} y {tmax} grados.{lluvia}"

    def _fetch(self) -> dict:
        r = self._client.get(
            _API,
            params={
                "latitude": self._loc.lat,
                "longitude": self._loc.lon,
                "current": "temperature_2m,weather_code,relative_humidity_2m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                "timezone": self._loc.timezone or "auto",
                "forecast_days": 3,
            },
        )
        r.raise_for_status()
        return r.json()
