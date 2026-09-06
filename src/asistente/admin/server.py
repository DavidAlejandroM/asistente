"""UI de administración web. FastAPI servido en un hilo dentro del proceso del asistente.

Sin login: pensada para la LAN de casa. Comparte los objetos vivos del orquestador.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from asistente.admin.logbus import LogBus, install
from asistente.config import AppConfig, load_config

log = logging.getLogger(__name__)

_HERE = Path(__file__).parent
_templates = Jinja2Templates(directory=str(_HERE / "templates"))


def _timer_service(orchestrator):
    skill = orchestrator.skills.get("manage_timers")
    return getattr(skill, "service", None)


def _timer_dicts(service) -> list[dict]:
    if service is None:
        return []
    import time

    now = time.time()
    return [
        {
            "id": t.id,
            "label": t.label,
            "kind": t.kind,
            "seconds_left": max(0, round(t.fire_at - now)),
        }
        for t in service.list()
    ]


def create_app(orchestrator, cfg_path: str | Path, log_bus: LogBus | None = None) -> FastAPI:
    cfg_path = Path(cfg_path)
    bus = log_bus or install()
    app = FastAPI(title="Asistente · administración")

    static_dir = _HERE / "static"
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    def dashboard(request: Request):
        skills = [
            {"name": s.name, "description": s.description,
             "enabled": orchestrator.skills.is_enabled(s.name)}
            for s in _all_skills(orchestrator)
        ]
        st = orchestrator.status()
        return _templates.TemplateResponse(
            request,
            "index.html",
            {
                "state": st.state.value if hasattr(st.state, "value") else str(st.state),
                "last_transcript": st.last_transcript,
                "last_response": st.last_response,
                "last_error": st.last_error,
                "skills": skills,
                "timers": _timer_dicts(_timer_service(orchestrator)),
                "config_yaml": cfg_path.read_text() if cfg_path.exists() else "",
            },
        )

    @app.get("/api/status")
    def api_status():
        st = orchestrator.status()
        return {
            "state": st.state.value if hasattr(st.state, "value") else str(st.state),
            "last_transcript": st.last_transcript,
            "last_response": st.last_response,
            "last_error": st.last_error,
            "updated_at": st.updated_at,
        }

    @app.get("/api/logs")
    def api_logs():
        return bus.history()

    @app.get("/api/logs/stream")
    def api_logs_stream():
        q = bus.subscribe()

        def gen():
            for line in bus.stream(q):
                yield f"data: {line}\n\n" if line else ": keepalive\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/api/skills/{name}/toggle")
    def toggle_skill(name: str):
        try:
            enabled_now = not orchestrator.skills.is_enabled(name)
            orchestrator.skills.toggle(name, enabled_now)
        except KeyError:
            raise HTTPException(404, f"skill desconocida: {name}")
        return {"name": name, "enabled": enabled_now}

    @app.get("/api/timers")
    def list_timers():
        return _timer_dicts(_timer_service(orchestrator))

    @app.post("/api/timers")
    def create_timer(seconds: float = Form(...), label: str = Form("")):
        svc = _timer_service(orchestrator)
        if svc is None:
            raise HTTPException(400, "la skill de temporizadores no está activa")
        t = svc.add_timer(seconds, label)
        return {"id": t.id}

    @app.post("/api/timers/{timer_id}/cancel")
    def cancel_timer(timer_id: str):
        svc = _timer_service(orchestrator)
        if svc is None or not svc.cancel(timer_id):
            raise HTTPException(404, "temporizador no encontrado")
        return {"ok": True}

    @app.post("/api/test-audio")
    def test_audio():
        orchestrator.announce("Prueba de sonido. Uno, dos, tres.")
        return {"ok": True}

    @app.get("/api/config")
    def get_config():
        return {"yaml": cfg_path.read_text() if cfg_path.exists() else ""}

    @app.post("/api/config")
    def save_config(yaml: str = Form(...)):
        tmp = cfg_path.with_suffix(".yaml.check")
        tmp.write_text(yaml)
        try:
            load_config(tmp)
        except Exception as exc:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            raise HTTPException(400, f"config inválida: {exc}")
        tmp.replace(cfg_path)
        return {"ok": True, "note": "guardado; reinicia el asistente para aplicar"}

    @app.post("/api/restart")
    def restart():
        try:
            subprocess.run(
                ["systemctl", "restart", "asistente"], check=True, timeout=10
            )
            return {"ok": True}
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(500, f"no se pudo reiniciar: {exc}")

    return app


def _all_skills(orchestrator):
    reg = orchestrator.skills
    return [reg.get(n) for n in reg.all_names()]


def start_admin_in_thread(cfg: AppConfig, orchestrator, cfg_path: str | Path) -> threading.Thread:
    import uvicorn

    bus = install()
    app = create_app(orchestrator, cfg_path, log_bus=bus)
    config = uvicorn.Config(
        app, host=cfg.admin.host, port=cfg.admin.port, log_level="warning"
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, name="admin", daemon=True)
    thread.start()
    log.info("UI de administración en http://%s:%s", cfg.admin.host, cfg.admin.port)
    return thread
