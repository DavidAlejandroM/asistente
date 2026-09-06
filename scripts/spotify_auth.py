#!/usr/bin/env python3
"""Obtiene el refresh_token de Spotify (flujo OAuth, una sola vez).

Pasos previos (gratis):
  1. https://developer.spotify.com/dashboard -> Create app
  2. Redirect URI:  http://127.0.0.1:8974/callback
  3. Copia Client ID y Client Secret

Uso:
  python scripts/spotify_auth.py --client-id XXX --client-secret YYY

Abre el navegador, autorizas, y el script imprime las líneas para tu .env.
"""

from __future__ import annotations

import argparse
import base64
import http.server
import secrets
import threading
import urllib.parse
import webbrowser

import httpx

REDIRECT = "http://127.0.0.1:8974/callback"
SCOPES = "user-modify-playback-state user-read-playback-state"
_AUTH = "https://accounts.spotify.com/authorize"
_TOKEN = "https://accounts.spotify.com/api/token"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--client-id", required=True)
    ap.add_argument("--client-secret", required=True)
    args = ap.parse_args()

    state = secrets.token_urlsafe(16)
    params = urllib.parse.urlencode(
        {
            "client_id": args.client_id,
            "response_type": "code",
            "redirect_uri": REDIRECT,
            "scope": SCOPES,
            "state": state,
        }
    )
    code_box: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                code_box["code"] = q["code"][0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write("Listo, ya puedes cerrar esta pestaña.".encode())
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *_):  # silencio
            pass

    server = http.server.HTTPServer(("127.0.0.1", 8974), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()

    url = f"{_AUTH}?{params}"
    print("Abriendo el navegador para autorizar...\n", url)
    webbrowser.open(url)

    while "code" not in code_box:
        pass

    basic = base64.b64encode(f"{args.client_id}:{args.client_secret}".encode()).decode()
    resp = httpx.post(
        _TOKEN,
        data={
            "grant_type": "authorization_code",
            "code": code_box["code"],
            "redirect_uri": REDIRECT,
        },
        headers={"Authorization": f"Basic {basic}"},
        timeout=15,
    )
    resp.raise_for_status()
    refresh = resp.json()["refresh_token"]

    print("\n--- Añade esto a tu .env ---")
    print(f"SPOTIFY_CLIENT_ID={args.client_id}")
    print(f"SPOTIFY_CLIENT_SECRET={args.client_secret}")
    print(f"SPOTIFY_REFRESH_TOKEN={refresh}")


if __name__ == "__main__":
    main()
