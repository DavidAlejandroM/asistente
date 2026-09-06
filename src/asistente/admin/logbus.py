"""Bus de logs en memoria para la UI: un buffer circular + suscriptores (SSE)."""

from __future__ import annotations

import logging
import queue
from collections import deque
from typing import Iterator

_FMT = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")


class LogBus(logging.Handler):
    def __init__(self, capacity: int = 300) -> None:
        super().__init__()
        self.setFormatter(_FMT)
        self._buffer: deque[str] = deque(maxlen=capacity)
        self._subscribers: list[queue.Queue[str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001
            return
        self._buffer.append(line)
        for q in list(self._subscribers):
            try:
                q.put_nowait(line)
            except queue.Full:
                pass

    def history(self) -> list[str]:
        return list(self._buffer)

    def subscribe(self) -> queue.Queue[str]:
        q: queue.Queue[str] = queue.Queue(maxsize=1000)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[str]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    def stream(self, q: queue.Queue[str], timeout: float = 15.0) -> Iterator[str]:
        """Genera líneas nuevas; emite '' de keepalive si no hay nada."""
        try:
            while True:
                try:
                    yield q.get(timeout=timeout)
                except queue.Empty:
                    yield ""  # keepalive
        finally:
            self.unsubscribe(q)


_ACTIVE: LogBus | None = None


def install(capacity: int = 300) -> LogBus:
    """Instala (una vez) el LogBus en el logger raíz y lo devuelve."""
    global _ACTIVE
    if _ACTIVE is None:
        _ACTIVE = LogBus(capacity)
        logging.getLogger().addHandler(_ACTIVE)
    return _ACTIVE
