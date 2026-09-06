import httpx
import pytest
import respx

from asistente.audio.wavutil import pcm_to_wav, wav_to_pcm
from asistente.stt.faster_whisper_http import FasterWhisperHTTP
from asistente.tts.piper_http import PiperHTTP

STT_URL = "http://pc:8001"
TTS_URL = "http://pc:8002"


@respx.mock
def test_stt_envia_wav_y_devuelve_texto():
    route = respx.post(f"{STT_URL}/transcribe").mock(
        return_value=httpx.Response(200, json={"text": "hola qué tal"})
    )
    stt = FasterWhisperHTTP(url=STT_URL, language="es")

    text = stt.transcribe(b"\x00\x01" * 800, sample_rate=16000)

    assert text == "hola qué tal"
    req = route.calls.last.request
    assert req.url.params["language"] == "es"
    body = req.read()
    assert body[:4] == b"RIFF"  # se manda un WAV, no PCM crudo
    pcm, rate = wav_to_pcm(body)
    assert rate == 16000


@respx.mock
def test_stt_error_de_red_da_mensaje_claro():
    respx.post(f"{STT_URL}/transcribe").mock(side_effect=httpx.ConnectError("no route"))
    stt = FasterWhisperHTTP(url=STT_URL, language="es")

    with pytest.raises(RuntimeError, match="STT"):
        stt.transcribe(b"\x00\x00", sample_rate=16000)


@respx.mock
def test_tts_pide_wav_y_devuelve_pcm_y_rate():
    wav = pcm_to_wav(b"\x03\x04" * 500, sample_rate=22050)
    route = respx.post(f"{TTS_URL}/speak").mock(
        return_value=httpx.Response(200, content=wav, headers={"content-type": "audio/wav"})
    )
    tts = PiperHTTP(url=TTS_URL, voice="es_ES-x-medium")

    pcm, rate = tts.synthesize("hola")

    assert rate == 22050
    assert pcm == b"\x03\x04" * 500
    import json

    sent = json.loads(route.calls.last.request.read())
    assert sent == {"text": "hola", "voice": "es_ES-x-medium"}


@respx.mock
def test_tts_error_http_da_mensaje_claro():
    respx.post(f"{TTS_URL}/speak").mock(return_value=httpx.Response(503, text="down"))
    tts = PiperHTTP(url=TTS_URL, voice="v")

    with pytest.raises(RuntimeError, match="TTS"):
        tts.synthesize("hola")
