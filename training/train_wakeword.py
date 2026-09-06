#!/usr/bin/env python3
"""Entrena una palabra de activación en español para openWakeWord.

NO se puede correr en la Pi ni en un portátil normal: necesita GPU (Google Colab
gratis sirve) y descarga varios GB de datos negativos. El resultado es un archivo
`.tflite` de ~1 MB que sí corre en la Pi Zero 2 W.

Uso (en Colab o una máquina con GPU):

    pip install openwakeword piper-phonemize
    git clone https://github.com/rhasspy/piper-sample-generator
    python training/train_wakeword.py --config training/wakeword.yaml

Pasos que hace:
  1. Genera miles de muestras TTS de la frase en español (piper-sample-generator).
  2. Descarga datos negativos/ruido/reverberación de openWakeWord (HuggingFace).
  3. Entrena y exporta `out/oye_asistente.tflite`.

Luego, en la Pi:
  cp out/oye_asistente.tflite ~/asistente/models/
  # config.yaml:
  wakeword:
    provider: openwakeword
    model: /home/pi/asistente/models/oye_asistente.tflite
    threshold: 0.5
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def generate_positives(cfg: dict, work: Path) -> Path:
    """Sintetiza muestras de la frase con piper-sample-generator (voces en español)."""
    out = work / "positives"
    out.mkdir(parents=True, exist_ok=True)
    gen = Path("piper-sample-generator")
    if not gen.exists():
        _run(["git", "clone", "https://github.com/rhasspy/piper-sample-generator", str(gen)])
        _run([sys.executable, "-m", "pip", "install", "-q", "-r", str(gen / "requirements.txt")])
        # checkpoint multi-idioma
        _run([
            "wget", "-nc", "-O", str(gen / "models" / "es_ES-glados.pt"),
            "https://github.com/rhasspy/piper-sample-generator/releases/download/v2.0.0/es_ES-glados.pt",
        ])

    for phrase in cfg["target_phrase"]:
        _run([
            sys.executable, str(gen / "generate_samples.py"),
            phrase,
            "--model", str(gen / "models" / "es_ES-glados.pt"),
            "--max-samples", str(cfg["n_samples"] // len(cfg["target_phrase"])),
            "--batch-size", str(cfg.get("tts_batch_size", 50)),
            "--output-dir", str(out),
        ])
    return out


def train(cfg_path: Path) -> None:
    """Delega en el pipeline oficial de openWakeWord."""
    try:
        from openwakeword.train import train_model
    except ImportError:
        raise SystemExit(
            "Falta openwakeword. Instala:  pip install openwakeword\n"
            "y ejecuta esto en Colab/GPU, no en la Pi."
        )
    train_model(config_path=str(cfg_path))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=Path("training/wakeword.yaml"))
    ap.add_argument("--work", type=Path, default=Path("wakeword_work"))
    ap.add_argument("--skip-positives", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(args.config.read_text())
    args.work.mkdir(exist_ok=True)

    if not args.skip_positives:
        pos = generate_positives(cfg, args.work)
        cfg["custom_positive_samples_path"] = str(pos)
        resolved = args.work / "wakeword.resolved.yaml"
        resolved.write_text(yaml.safe_dump(cfg))
        args.config = resolved

    train(args.config)
    print("\nListo. Copia out/%s.tflite a la Pi (models/)." % cfg["model_name"])


if __name__ == "__main__":
    main()
