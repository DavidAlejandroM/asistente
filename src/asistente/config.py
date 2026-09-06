"""Carga y validación de ``config.yaml``.

Cada pieza intercambiable se describe con ``provider`` + parámetros libres. La
factory (``app.py``) usa ``provider`` para elegir la clase y le pasa ``settings``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class ProviderConfig(BaseModel):
    """``{provider: nombre, ...parámetros}``. Los parámetros quedan en ``settings``."""

    model_config = ConfigDict(extra="allow")

    provider: str

    @property
    def settings(self) -> dict[str, Any]:
        extra = dict(self.__pydantic_extra__ or {})
        return extra


class LocationConfig(BaseModel):
    lat: float = 0.0
    lon: float = 0.0
    name: str = ""
    timezone: str = "auto"  # p. ej. "America/Bogota"; "auto" = que lo deduzca Open-Meteo


class AdminConfig(BaseModel):
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 8080


class AudioConfig(BaseModel):
    source: str = "sounddevice"
    sink: str = "sounddevice"
    recorder: str = "vad"
    input_device: str | int | None = None
    output_device: str | int | None = None


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    llm: ProviderConfig
    stt: ProviderConfig
    tts: ProviderConfig
    wakeword: ProviderConfig
    location: LocationConfig = Field(default_factory=LocationConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    audio: AudioConfig = Field(default_factory=AudioConfig)
    skills: dict[str, dict[str, Any]] = Field(default_factory=dict)
    disabled_skills: list[str] = Field(default_factory=list)

    system_prompt: str = (
        "Eres un asistente de voz en español. Responde de forma breve y natural, "
        "como para ser escuchado en voz alta. Usa las herramientas disponibles cuando "
        "la petición lo requiera."
    )
    wake_response: str = ""  # frase corta al detectar la palabra de activación (opcional)
    wake_beep: bool = True    # pitido corto al activarse
    sample_rate: int = 16000

    @model_validator(mode="after")
    def _no_dummy_location_for_weather(self) -> AppConfig:
        return self


def load_dotenv(path: str | Path) -> None:
    """Carga ``KEY=VALUE`` de un ``.env`` en ``os.environ`` (no pisa lo ya definido)."""
    import os

    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(path: str | Path) -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    try:
        return AppConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"config.yaml inválido:\n{exc}") from exc


def dump_config(cfg: AppConfig, path: str | Path) -> None:
    """Escribe la config de vuelta a disco de forma atómica."""
    target = Path(path)
    data = cfg.model_dump(mode="json", exclude_defaults=False)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    tmp.replace(target)
