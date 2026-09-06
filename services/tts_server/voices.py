"""Descarga de voces Piper desde el repo público rhasspy/piper-voices (HuggingFace).

El nombre de una voz sigue el patrón ``<lang>-<name>-<quality>`` (p. ej.
``es_ES-sharvard-medium``) y su ruta en el repo es
``<familia>/<lang>/<name>/<quality>/<voz>.onnx``.
"""

from __future__ import annotations

from pathlib import Path

import requests

_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


def _repo_dir(voice: str) -> str:
    lang, name, quality = voice.split("-", 2)
    family = lang.split("_")[0]
    return f"{family}/{lang}/{name}/{quality}"


def ensure_voice(voice: str, voices_dir: Path) -> Path:
    """Devuelve la ruta al .onnx, descargándolo (y su .json) si falta."""
    voices_dir.mkdir(parents=True, exist_ok=True)
    onnx = voices_dir / f"{voice}.onnx"
    config = voices_dir / f"{voice}.onnx.json"
    if onnx.exists() and config.exists():
        return onnx

    repo_dir = _repo_dir(voice)
    for target, suffix in ((onnx, ".onnx"), (config, ".onnx.json")):
        if target.exists():
            continue
        url = f"{_BASE}/{repo_dir}/{voice}{suffix}"
        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        target.write_bytes(resp.content)
    return onnx
