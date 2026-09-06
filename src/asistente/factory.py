"""Factory: convierte un ``AppConfig`` en objetos vivos.

Cada interfaz tiene un registro ``{nombre_proveedor: builder}``. Un builder recibe el
dict de ``settings`` (y a veces el ``AppConfig`` entero) y devuelve la instancia.
Registrar un proveedor nuevo = una línea, sin tocar el resto.
"""

from __future__ import annotations

import logging
from typing import Callable

from asistente.brain import Brain
from asistente.config import AppConfig
from asistente.orchestrator import Orchestrator
from asistente.skills.registry import SkillRegistry

log = logging.getLogger(__name__)

Builder = Callable[[dict], object]

_LLM: dict[str, Builder] = {}
_STT: dict[str, Builder] = {}
_TTS: dict[str, Builder] = {}
_WAKEWORD: dict[str, Builder] = {}
_RECORDER: dict[str, Builder] = {}
_AUDIO_SOURCE: dict[str, Builder] = {}
_AUDIO_SINK: dict[str, Builder] = {}

# Builders de skills: (AppConfig) -> Skill | None. None = no configurada.
SkillBuilder = Callable[[AppConfig], object | None]
_SKILLS: list[SkillBuilder] = []


def register_llm(name: str, builder: Builder) -> None:
    _LLM[name] = builder


def register_stt(name: str, builder: Builder) -> None:
    _STT[name] = builder


def register_tts(name: str, builder: Builder) -> None:
    _TTS[name] = builder


def register_wakeword(name: str, builder: Builder) -> None:
    _WAKEWORD[name] = builder


def register_recorder(name: str, builder: Builder) -> None:
    _RECORDER[name] = builder


def register_audio_source(name: str, builder: Builder) -> None:
    _AUDIO_SOURCE[name] = builder


def register_audio_sink(name: str, builder: Builder) -> None:
    _AUDIO_SINK[name] = builder


def register_skill(builder: SkillBuilder) -> None:
    _SKILLS.append(builder)


def _pick(registry: dict[str, Builder], kind: str, provider: str, settings: dict):
    if provider not in registry:
        raise ValueError(
            f"proveedor de {kind} desconocido: '{provider}'. "
            f"Disponibles: {sorted(registry)}"
        )
    return registry[provider](settings)


def build_skills(cfg: AppConfig) -> SkillRegistry:
    registry = SkillRegistry()
    for builder in _SKILLS:
        try:
            skill = builder(cfg)
        except Exception:  # noqa: BLE001
            log.exception("no se pudo construir una skill; se omite")
            continue
        if skill is None:
            continue
        registry.register(skill)
        if skill.name in cfg.disabled_skills:
            registry.toggle(skill.name, False)
    return registry


def build_brain(cfg: AppConfig, skills: SkillRegistry | None = None) -> Brain:
    llm = _pick(_LLM, "llm", cfg.llm.provider, cfg.llm.settings)
    skills = skills if skills is not None else build_skills(cfg)
    return Brain(llm=llm, skills=skills, system_prompt=cfg.system_prompt)


def build_orchestrator(cfg: AppConfig, brain: Brain | None = None) -> Orchestrator:
    brain = brain or build_brain(cfg)
    audio = {
        "sample_rate": cfg.sample_rate,
        "input_device": cfg.audio.input_device,
        "output_device": cfg.audio.output_device,
    }
    orchestrator = Orchestrator(
        audio_source=_pick(_AUDIO_SOURCE, "audio_source", cfg.audio.source, audio),
        wakeword=_pick(_WAKEWORD, "wakeword", cfg.wakeword.provider, cfg.wakeword.settings),
        recorder=_pick(_RECORDER, "recorder", cfg.audio.recorder, audio),
        stt=_pick(_STT, "stt", cfg.stt.provider, cfg.stt.settings),
        brain=brain,
        tts=_pick(_TTS, "tts", cfg.tts.provider, cfg.tts.settings),
        sink=_pick(_AUDIO_SINK, "audio_sink", cfg.audio.sink, audio),
        sample_rate=cfg.sample_rate,
        wake_response=cfg.wake_response,
        wake_beep=cfg.wake_beep,
    )

    for skill in brain.skills.enabled_skills():
        binder = getattr(skill, "bind_orchestrator", None)
        if callable(binder):
            binder(orchestrator)

    return orchestrator


# --- proveedores fake (sin hardware ni red): demo y tests --------------------

def _install_fakes() -> None:
    from asistente.fakes import (
        EchoLLM,
        FakeAudioSink,
        FakeAudioSource,
        FakeRecorder,
        FakeSTT,
        FakeTTS,
        FakeWakeWord,
    )

    register_llm("fake", lambda s: EchoLLM())
    register_stt("fake", lambda s: FakeSTT(s.get("transcript", "hola asistente")))
    register_tts("fake", lambda s: FakeTTS())
    register_wakeword("fake", lambda s: FakeWakeWord(b"WAKE"))
    # "none": nunca se dispara. Para modo push-to-talk (--ptt), sin openWakeWord.
    register_wakeword("none", lambda s: FakeWakeWord(b"\x00__nunca__\x00"))
    register_recorder("fake", lambda s: FakeRecorder(b"AUDIO"))
    register_audio_source("fake", lambda s: FakeAudioSource([b"WAKE", b"x"]))
    register_audio_sink("fake", lambda s: FakeAudioSink())


_install_fakes()


# --- proveedores reales de red (no necesitan hardware de audio) -------------

def _install_network_providers() -> None:
    from asistente.llm.ollama_client import OllamaClient
    from asistente.stt.faster_whisper_http import FasterWhisperHTTP
    from asistente.tts.piper_http import PiperHTTP

    register_llm(
        "ollama",
        lambda s: OllamaClient(url=s["url"], model=s["model"], timeout=s.get("timeout", 120.0)),
    )
    register_stt(
        "faster_whisper_http",
        lambda s: FasterWhisperHTTP(url=s["url"], language=s.get("language", "es")),
    )
    register_tts(
        "piper_http",
        lambda s: PiperHTTP(url=s["url"], voice=s.get("voice", "es_ES-sharvard-medium")),
    )


_install_network_providers()


# --- hardware de audio de la Pi (sounddevice / openWakeWord / VAD) ----------

def _install_audio_providers() -> None:
    def _source(s):
        from asistente.audio.source_sounddevice import SoundDeviceSource

        return SoundDeviceSource(
            sample_rate=s.get("sample_rate", 16000), device=s.get("input_device")
        )

    def _sink(s):
        from asistente.audio.sink_sounddevice import SoundDeviceSink

        return SoundDeviceSink(device=s.get("output_device"))

    def _vad(s):
        from asistente.audio.vad import VadRecorder, WebrtcVad

        rate = s.get("sample_rate", 16000)
        return VadRecorder(vad=WebrtcVad(sample_rate=rate), sample_rate=rate)

    def _oww(s):
        from asistente.wakeword.openwakeword_detector import OpenWakeWordDetector

        return OpenWakeWordDetector(
            model=s.get("model", "hey_jarvis"),
            threshold=s.get("threshold", 0.5),
            framework=s.get("framework", "tflite"),
        )

    def _vosk(s):
        from asistente.wakeword.vosk_wakeword import VoskWakeWord

        phrases = s.get("phrases") or ([s["phrase"]] if s.get("phrase") else ["hey paco"])
        return VoskWakeWord(
            phrases=phrases,
            model_path=s.get("model_path"),
            language=s.get("language", "es"),
            sample_rate=s.get("sample_rate", 16000),
        )

    register_audio_source("sounddevice", _source)
    register_audio_sink("sounddevice", _sink)
    register_recorder("vad", _vad)
    register_wakeword("openwakeword", _oww)
    register_wakeword("vosk", _vosk)


_install_audio_providers()


# --- skills incorporadas ---------------------------------------------------

def _install_skills() -> None:
    import os
    from pathlib import Path

    from asistente.skills.home_assistant import HomeAssistantSkill
    from asistente.skills.spotify import SpotifySkill
    from asistente.skills.timers import TimerService, TimerSkill
    from asistente.skills.weather import WeatherSkill

    def _weather(cfg: AppConfig):
        if cfg.location.lat == 0.0 and cfg.location.lon == 0.0:
            return None
        return WeatherSkill(cfg.location)

    def _timers(cfg: AppConfig):
        tz = cfg.location.timezone if cfg.location.timezone not in ("", "auto") else "UTC"
        path = Path.home() / ".asistente" / "timers.json"
        service = TimerService(on_expire=lambda t: None, storage_path=path, tz=tz)
        return TimerSkill(service)

    def _home_assistant(cfg: AppConfig):
        conf = cfg.skills.get("home_assistant") or {}
        url = conf.get("url")
        token = conf.get("token") or os.getenv("HOME_ASSISTANT_TOKEN", "")
        if not url or not token:
            return None
        return HomeAssistantSkill(url=url, token=token)

    def _spotify(cfg: AppConfig):
        conf = cfg.skills.get("spotify") or {}
        cid = conf.get("client_id") or os.getenv("SPOTIFY_CLIENT_ID", "")
        secret = conf.get("client_secret") or os.getenv("SPOTIFY_CLIENT_SECRET", "")
        refresh = conf.get("refresh_token") or os.getenv("SPOTIFY_REFRESH_TOKEN", "")
        if not (cid and secret and refresh):
            return None
        return SpotifySkill(
            client_id=cid,
            client_secret=secret,
            refresh_token=refresh,
            device_name=conf.get("device_name", "asistente"),
        )

    register_skill(_weather)
    register_skill(_timers)
    register_skill(_home_assistant)
    register_skill(_spotify)


_install_skills()
