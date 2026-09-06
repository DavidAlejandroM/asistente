import httpx
import respx

from asistente.skills.spotify import SpotifySkill

TOKEN_URL = "https://accounts.spotify.com/api/token"
API = "https://api.spotify.com/v1"


def _skill():
    return SpotifySkill(
        client_id="cid",
        client_secret="secret",
        refresh_token="refresh",
        device_name="asistente",
    )


def _mock_token():
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "AT", "expires_in": 3600})
    )


def _mock_devices(active=False):
    respx.get(f"{API}/me/player/devices").mock(
        return_value=httpx.Response(
            200,
            json={"devices": [
                {"id": "dev1", "name": "asistente", "is_active": active},
                {"id": "dev2", "name": "Móvil", "is_active": False},
            ]},
        )
    )


@respx.mock
def test_play_busca_la_cancion_y_la_reproduce_en_el_dispositivo():
    _mock_token()
    _mock_devices(active=True)
    respx.get(f"{API}/search").mock(
        return_value=httpx.Response(200, json={
            "tracks": {"items": [
                {"uri": "spotify:track:abc", "name": "Song", "artists": [{"name": "Artista"}]}
            ]}
        })
    )
    play = respx.put(f"{API}/me/player/play").mock(return_value=httpx.Response(204))

    out = _skill().run({"action": "play", "query": "Song de Artista"})

    assert play.called
    body = play.calls.last.request.read().decode()
    assert "spotify:track:abc" in body
    assert play.calls.last.request.url.params["device_id"] == "dev1"
    assert "Song" in out and "Artista" in out
    assert respx.calls[0].request.headers["authorization"].startswith("Basic ")


@respx.mock
def test_play_transfiere_reproduccion_si_el_dispositivo_no_esta_activo():
    _mock_token()
    _mock_devices(active=False)
    transfer = respx.put(f"{API}/me/player").mock(return_value=httpx.Response(204))
    respx.get(f"{API}/search").mock(
        return_value=httpx.Response(200, json={"tracks": {"items": [
            {"uri": "spotify:track:x", "name": "N", "artists": [{"name": "A"}]}]}})
    )
    respx.put(f"{API}/me/player/play").mock(return_value=httpx.Response(204))

    _skill().run({"action": "play", "query": "algo"})

    assert transfer.called


@respx.mock
def test_pause_llama_al_endpoint_de_pausa():
    _mock_token()
    _mock_devices(active=True)
    pause = respx.put(f"{API}/me/player/pause").mock(return_value=httpx.Response(204))

    out = _skill().run({"action": "pause"})

    assert pause.called
    assert "pausa" in out.lower() or "pausado" in out.lower()


@respx.mock
def test_volumen():
    _mock_token()
    _mock_devices(active=True)
    vol = respx.put(f"{API}/me/player/volume").mock(return_value=httpx.Response(204))

    _skill().run({"action": "volume", "volume": 40})

    assert vol.called
    assert vol.calls.last.request.url.params["volume_percent"] == "40"


@respx.mock
def test_sin_resultados_de_busqueda():
    _mock_token()
    _mock_devices(active=True)
    respx.get(f"{API}/search").mock(
        return_value=httpx.Response(200, json={"tracks": {"items": []}})
    )
    out = _skill().run({"action": "play", "query": "asdfghjkl"})
    assert "no" in out.lower()


@respx.mock
def test_error_de_api_es_amable():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    out = _skill().run({"action": "pause"})
    assert "no" in out.lower() and "spotify" in out.lower()
