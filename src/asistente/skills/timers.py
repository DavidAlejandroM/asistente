"""Temporizadores y alarmas: estado local, persistido, con hilo de vigilancia.

``TimerService`` mantiene la lista y dispara ``on_expire(Timer)`` al vencer.
``TimerSkill`` la expone al LLM como tools. El cableado (qué sonido suena) lo
decide quien construye el servicio, pasando el callback.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)


@dataclass
class Timer:
    id: str
    label: str
    fire_at: float  # epoch segundos
    kind: str  # "timer" | "alarm"
    created_at: float = field(default_factory=time.time)


class TimerService:
    def __init__(
        self,
        on_expire: Callable[[Timer], None],
        *,
        clock: Callable[[], float] = time.time,
        storage_path: str | Path | None = None,
        tz: str = "UTC",
    ) -> None:
        self._on_expire = on_expire
        self._clock = clock
        self._path = Path(storage_path) if storage_path else None
        self._tz = tz
        self._timers: dict[str, Timer] = {}
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._load()

    # -- API para la skill --------------------------------------------------
    def add_timer(self, seconds: float, label: str = "") -> Timer:
        return self._add(self._clock() + float(seconds), label, "timer")

    def add_alarm(self, hhmm: str, label: str = "") -> Timer:
        return self._add(self._next_occurrence(hhmm), label, "alarm")

    def set_on_expire(self, callback: Callable[[Timer], None]) -> None:
        self._on_expire = callback

    def cancel(self, timer_id: str) -> bool:
        with self._lock:
            existed = self._timers.pop(timer_id, None) is not None
        if existed:
            self._persist()
        return existed

    def list(self) -> list[Timer]:
        with self._lock:
            return sorted(self._timers.values(), key=lambda t: t.fire_at)

    # -- vigilancia -------------------------------------------------------
    def tick(self) -> None:
        now = self._clock()
        with self._lock:
            due = [t for t in self._timers.values() if t.fire_at <= now]
            for t in due:
                self._timers.pop(t.id, None)
        for t in due:
            self._fire(t)
        if due:
            self._persist()

    def start(self, interval: float = 1.0) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()

        def _loop() -> None:
            while not self._stop.wait(interval):
                try:
                    self.tick()
                except Exception:  # noqa: BLE001
                    log.exception("fallo en el tick de temporizadores")

        self._thread = threading.Thread(target=_loop, name="timers", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    # -- internos --------------------------------------------------------
    def _add(self, fire_at: float, label: str, kind: str) -> Timer:
        t = Timer(id=uuid.uuid4().hex[:8], label=label, fire_at=fire_at, kind=kind,
                  created_at=self._clock())
        with self._lock:
            self._timers[t.id] = t
        self._persist()
        return t

    def _fire(self, t: Timer) -> None:
        try:
            self._on_expire(t)
        except Exception:  # noqa: BLE001
            log.exception("on_expire lanzó para %s", t.id)

    def _next_occurrence(self, hhmm: str) -> float:
        hh, mm = (int(x) for x in hhmm.strip().split(":"))
        now_dt = datetime.fromtimestamp(self._clock(), ZoneInfo(self._tz))
        target = now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if target <= now_dt:
            target += timedelta(days=1)
        return target.timestamp()

    def _load(self) -> None:
        if not self._path or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            log.warning("no se pudo leer %s; se ignora", self._path)
            return
        now = self._clock()
        expired: list[Timer] = []
        for raw in data:
            t = Timer(**raw)
            if t.fire_at <= now:
                expired.append(t)
            else:
                self._timers[t.id] = t
        for t in expired:
            self._fire(t)
        if expired:
            self._persist()

    def _persist(self) -> None:
        if not self._path:
            return
        with self._lock:
            payload = [asdict(t) for t in self._timers.values()]
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        tmp.replace(self._path)


def _human_delta(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 60:
        return f"{seconds} segundos"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    parts = []
    if h:
        parts.append(f"{h} hora" + ("s" if h != 1 else ""))
    if m:
        parts.append(f"{m} minuto" + ("s" if m != 1 else ""))
    if s and not h:
        parts.append(f"{s} segundos")
    return " y ".join(parts) if parts else "0 segundos"


class TimerSkill:
    name = "manage_timers"
    description = (
        "Crea, lista o cancela temporizadores y alarmas. "
        "Para 'ponme 10 minutos' usa action=set_timer con seconds=600. "
        "Para 'despiértame a las 7:30' usa action=set_alarm con time='07:30'."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set_timer", "set_alarm", "list", "cancel"],
            },
            "seconds": {"type": "number", "description": "duración total en segundos (set_timer)"},
            "time": {"type": "string", "description": "hora HH:MM en 24h (set_alarm)"},
            "label": {"type": "string", "description": "nombre opcional"},
            "id": {"type": "string", "description": "id del temporizador a cancelar"},
        },
        "required": ["action"],
    }

    def __init__(self, service: TimerService, clock: Callable[[], float] = time.time) -> None:
        self.service = service
        self._svc = service
        self._clock = clock

    def bind_orchestrator(self, orchestrator) -> None:
        """Cablea el sonido de alarma y arranca la vigilancia en segundo plano."""

        def _ring(t: Timer) -> None:
            if t.kind == "alarm":
                msg = f"Es la hora{': ' + t.label if t.label else ''}."
            else:
                msg = f"Se acabó el tiempo{' de ' + t.label if t.label else ''}."
            orchestrator.announce(msg)

        self._svc.set_on_expire(_ring)
        self._svc.start()

    def run(self, args: dict) -> str:
        action = args.get("action")
        label = args.get("label", "") or ""

        if action == "set_timer":
            seconds = float(args.get("seconds") or 0)
            if seconds <= 0:
                return "¿De cuánto tiempo quieres el temporizador?"
            self._svc.add_timer(seconds, label)
            nombre = f" para {label}" if label else ""
            return f"Temporizador{nombre} puesto: {_human_delta(seconds)}."

        if action == "set_alarm":
            hhmm = str(args.get("time") or "").strip()
            if ":" not in hhmm:
                return "¿A qué hora quieres la alarma?"
            t = self._svc.add_alarm(hhmm, label)
            when = datetime.fromtimestamp(t.fire_at).strftime("%H:%M")
            return f"Alarma puesta para las {when}."

        if action == "list":
            timers = self._svc.list()
            if not timers:
                return "No tienes temporizadores ni alarmas activos."
            now = self._clock()
            lines = []
            for t in timers:
                restante = _human_delta(max(0, t.fire_at - now))
                etiqueta = f" ({t.label})" if t.label else ""
                tipo = "Alarma" if t.kind == "alarm" else "Temporizador"
                lines.append(f"{tipo}{etiqueta}: faltan {restante} [id {t.id}]")
            return ". ".join(lines) + "."

        if action == "cancel":
            timer_id = str(args.get("id") or "")
            if self._svc.cancel(timer_id):
                return "Cancelado."
            return "No encuentro ese temporizador."

        return "No he entendido qué hacer con los temporizadores."
