"""Skill de Spotify: controla la reproducción vía la Web API.

El reproductor real es un dispositivo Spotify Connect (librespot/spotifyd) que corre
en la Pi y saca el audio al altavoz Bluetooth. Esta skill busca canciones y manda
play/pause/next/volume a ese dispositivo.

Requiere cuenta Premium y una app registrada en developer.spotify.com (gratis).
Credenciales en .env: SPOTIFY_CLIENT_ID / SECRET / REFRESH_TOKEN.
"""

from __future__ import annotations

import base64
import logging
import time

import httpx

log = logging.getLogger(__name__)

_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API = "https://api.spotify.com/v1"


class _Auth(httpx.Auth):
    """Añade el Bearer y refresca el token cuando caduca."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self._basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        self._refresh_token = refresh_token
        self._access_token = ""
        self._expires_at = 0.0

    def _refresh(self) -> None:
        resp = httpx.post(
            _TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            headers={"Authorization": f"Basic {self._basic}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600) - 60

    def auth_flow(self, request):
        if time.time() >= self._expires_at:
            self._refresh()
        request.headers["Authorization"] = f"Bearer {self._access_token}"
        yield request


class SpotifySkill:
    name = "spotify_control"
    description = (
        "Reproduce música en Spotify y controla la reproducción. "
        "action=play con query para poner una canción; play sin query reanuda."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["play", "pause", "next", "previous", "volume"],
            },
            "query": {"type": "string", "description": "canción y/o artista a buscar"},
            "volume": {"type": "integer", "description": "volumen 0-100"},
        },
        "required": ["action"],
    }

    def __init__(self, client_id, client_secret, refresh_token, device_name, timeout=15.0):
        self._device_name = device_name
        self._client = httpx.Client(
            timeout=timeout,
            auth=_Auth(client_id, client_secret, refresh_token),
        )

    # -- helpers -------------------------------------------------------
    def _device(self) -> dict | None:
        r = self._client.get(f"{_API}/me/player/devices")
        r.raise_for_status()
        devices = r.json().get("devices", [])
        for d in devices:
            if d.get("name", "").lower() == self._device_name.lower():
                return d
        return devices[0] if devices else None

    def _ensure_active(self, device: dict) -> None:
        if not device.get("is_active"):
            self._client.put(f"{_API}/me/player", json={"device_ids": [device["id"]], "play": False})

    def _search_track(self, query: str) -> dict | None:
        r = self._client.get(
            f"{_API}/search", params={"q": query, "type": "track", "limit": 1}
        )
        r.raise_for_status()
        items = r.json().get("tracks", {}).get("items", [])
        return items[0] if items else None

    # -- skill --------------------------------------------------------
    def run(self, args: dict) -> str:
        action = args.get("action")
        try:
            device = self._device()
            if device is None:
                return "No encuentro ningún dispositivo de Spotify disponible."

            if action == "play":
                return self._play(device, args.get("query"))
            if action == "pause":
                self._client.put(f"{_API}/me/player/pause", params={"device_id": device["id"]})
                return "Música en pausa."
            if action == "next":
                self._client.post(f"{_API}/me/player/next", params={"device_id": device["id"]})
                return "Siguiente canción."
            if action == "previous":
                self._client.post(
                    f"{_API}/me/player/previous", params={"device_id": device["id"]}
                )
                return "Canción anterior."
            if action == "volume":
                vol = max(0, min(100, int(args.get("volume", 50))))
                self._client.put(
                    f"{_API}/me/player/volume",
                    params={"volume_percent": vol, "device_id": device["id"]},
                )
                return f"Volumen al {vol}%."
            return "No he entendido qué hacer con Spotify."
        except httpx.HTTPError as exc:
            log.warning("Spotify falló: %s", exc)
            return "No puedo controlar Spotify ahora mismo."

    def _play(self, device: dict, query: str | None) -> str:
        self._ensure_active(device)
        if not query:
            self._client.put(f"{_API}/me/player/play", params={"device_id": device["id"]})
            return "Reanudando la música."

        track = self._search_track(query)
        if track is None:
            return f"No he encontrado «{query}» en Spotify."
        self._client.put(
            f"{_API}/me/player/play",
            params={"device_id": device["id"]},
            json={"uris": [track["uri"]]},
        )
        artist = track["artists"][0]["name"] if track.get("artists") else ""
        return f"Reproduciendo {track['name']}" + (f" de {artist}." if artist else ".")
