"""Punto de entrada / CLI.

Modos:
  asistente              -> bucle normal (wake word en bucle)
  asistente --once       -> atiende una sola petición y sale
  asistente --text       -> teclear en vez de hablar (desarrollo, no necesita audio)
  asistente --fake       -> usa proveedores fake (sin hardware ni red)

La UI de administración se levanta en paralelo si ``admin.enabled`` (salvo --text).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from asistente.config import AppConfig, load_config, load_dotenv
from asistente.factory import build_brain, build_orchestrator

log = logging.getLogger(__name__)


def _force_fake(cfg: AppConfig) -> AppConfig:
    for section in (cfg.llm, cfg.stt, cfg.tts, cfg.wakeword):
        section.provider = "fake"
    cfg.audio.source = cfg.audio.sink = cfg.audio.recorder = "fake"
    return cfg


def run_text(cfg: AppConfig, stdin=None, stdout=None) -> None:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    brain = build_brain(cfg)
    print("Modo texto. Escribe y pulsa Enter (Ctrl-D para salir).", file=stdout)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        print(f"< {brain.process(line)}", file=stdout, flush=True)


def _maybe_start_admin(cfg: AppConfig, orchestrator, cfg_path: Path):
    if not cfg.admin.enabled:
        return
    try:
        from asistente.admin.server import start_admin_in_thread
    except ImportError:
        log.warning("UI de administración no disponible (falta el extra [admin]); se omite")
        return
    start_admin_in_thread(cfg, orchestrator, cfg_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asistente")
    parser.add_argument("-c", "--config", default="config.yaml", type=Path)
    parser.add_argument("--text", action="store_true", help="modo teclado (sin audio)")
    parser.add_argument(
        "--ptt", action="store_true",
        help="push-to-talk: pulsa Enter para hablar, sin palabra de activación",
    )
    parser.add_argument("--once", action="store_true", help="una sola interacción")
    parser.add_argument("--fake", action="store_true", help="proveedores fake")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    load_dotenv(args.config.parent / ".env")
    load_dotenv(".env")
    cfg = load_config(args.config)
    if args.fake:
        cfg = _force_fake(cfg)

    if args.text:
        run_text(cfg)
        return 0

    if args.ptt:
        cfg.wakeword.provider = "none"  # push-to-talk no necesita palabra de activación

    orchestrator = build_orchestrator(cfg)
    _maybe_start_admin(cfg, orchestrator, args.config)

    try:
        if args.ptt:
            print("Push-to-talk. Pulsa Enter para hablar (Ctrl-C para salir).")
            while True:
                input()
                orchestrator.interact_once()
        elif args.once:
            orchestrator.run_once()
        else:
            orchestrator.run_forever()
    except (KeyboardInterrupt, EOFError):
        log.info("interrumpido")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
