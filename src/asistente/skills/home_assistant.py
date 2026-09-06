"""Skill de domótica vía la API REST de Home Assistant."""

from __future__ import annotations

import json
import logging
import time

import httpx

log = logging.getLogger(__name__)

# Dominios que tiene sentido encender/apagar por voz
_CONTROLLABLE = {
    "light", "switch", "fan", "cover", "climate", "media_player",
    "scene", "script", "input_boolean", "automation",
}
_ACTION_SERVICE = {"on": "turn_on", "off": "turn_off", "toggle": "toggle"}


class HomeAssistantSkill:
    name = "home_control"
    description = (
        "Controla dispositivos de casa (luces, enchufes, etc.) vía Home Assistant. "
        "action=list para enumerar lo disponible."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["on", "off", "toggle", "list"]},
            "target": {
                "type": "string",
                "description": "nombre del dispositivo tal y como lo diría una persona",
            },
        },
        "required": ["action"],
    }

    def __init__(self, url: str, token: str, cache_ttl: float = 30.0, timeout: float = 10.0):
        self._url = url.rstrip("/")
        self._token = token
        self._cache_ttl = cache_ttl
        self._client = httpx.Client(
            timeout=timeout, headers={"Authorization": f"Bearer {token}"}
        )
        self._entities: list[dict] = []
        self._fetched_at = 0.0

    # -- API HA ----------------------------------------------------------
    def _states(self, force: bool = False) -> list[dict]:
        if not force and self._entities and time.time() - self._fetched_at < self._cache_ttl:
            return self._entities
        r = self._client.get(f"{self._url}/api/states")
        r.raise_for_status()
        self._entities = [
            {
                "entity_id": s["entity_id"],
                "domain": s["entity_id"].split(".")[0],
                "name": s.get("attributes", {}).get("friendly_name", s["entity_id"]),
                "state": s.get("state"),
            }
            for s in r.json()
            if s["entity_id"].split(".")[0] in _CONTROLLABLE
        ]
        self._fetched_at = time.time()
        return self._entities

    def _match(self, target: str) -> dict | None:
        target = (target or "").strip().lower()
        if not target:
            return None
        entities = self._states()
        for e in entities:  # id exacto
            if e["entity_id"].lower() == target:
                return e
        for e in entities:  # nombre exacto
            if e["name"].lower() == target:
                return e
        # coincidencia parcial por palabras
        best = None
        for e in entities:
            name = e["name"].lower()
            if target in name or name in target:
                best = e
                break
        return best

    def _call_service(self, domain: str, service: str, entity_id: str) -> None:
        r = self._client.post(
            f"{self._url}/api/services/{domain}/{service}",
            content=json.dumps({"entity_id": entity_id}),
            headers={"Content-Type": "application/json"},
        )
        r.raise_for_status()

    # -- skill ---------------------------------------------------------
    def run(self, args: dict) -> str:
        action = args.get("action")
        try:
            if action == "list":
                names = [e["name"] for e in self._states(force=True)]
                if not names:
                    return "No veo dispositivos controlables en Home Assistant."
                return "Puedes controlar: " + ", ".join(names) + "."

            if action not in _ACTION_SERVICE:
                return "No he entendido qué hacer con la casa."

            entity = self._match(args.get("target", ""))
            if entity is None:
                return f"No encuentro ningún dispositivo que se llame «{args.get('target')}»."

            self._call_service(entity["domain"], _ACTION_SERVICE[action], entity["entity_id"])
            verbo = {"on": "Encendido", "off": "Apagado", "toggle": "Cambiado"}[action]
            return f"{verbo}: {entity['name']}."
        except httpx.HTTPError as exc:
            log.warning("Home Assistant falló: %s", exc)
            return "No puedo contactar con Home Assistant ahora mismo."
