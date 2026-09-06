import json

from asistente.skills.timers import TimerService


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def test_add_timer_y_tick_dispara_al_vencer():
    clock = FakeClock(1000.0)
    fired = []
    svc = TimerService(on_expire=fired.append, clock=clock)

    t = svc.add_timer(60, label="pasta")
    assert svc.list() == [t]

    clock.now = 1059
    svc.tick()
    assert fired == []

    clock.now = 1061
    svc.tick()
    assert [f.id for f in fired] == [t.id]
    assert svc.list() == []  # se elimina tras dispararse


def test_cancel_elimina_el_timer():
    svc = TimerService(on_expire=lambda t: None, clock=FakeClock())
    t = svc.add_timer(60)
    assert svc.cancel(t.id) is True
    assert svc.list() == []
    assert svc.cancel("noexiste") is False


def test_add_alarm_calcula_proxima_ocurrencia_en_su_zona():
    # epoch 1704110400 == 2024-01-01 12:00:00 UTC == 07:00:00 America/Bogota (UTC-5)
    clock = FakeClock(1704110400.0)
    svc = TimerService(on_expire=lambda t: None, clock=clock, tz="America/Bogota")

    a = svc.add_alarm("07:30", label="despertar")
    assert a.fire_at == 1704110400.0 + 0.5 * 3600  # hoy a las 07:30 -> +30 min

    # si la hora ya pasó hoy, va a mañana
    b = svc.add_alarm("04:00")
    assert b.fire_at == 1704110400.0 + 21 * 3600  # mañana 04:00 -> +21h


def test_persiste_y_recarga_de_disco(tmp_path):
    path = tmp_path / "timers.json"
    clock = FakeClock(1000.0)
    svc = TimerService(on_expire=lambda t: None, clock=clock, storage_path=path)
    t = svc.add_timer(120, label="té")

    assert json.loads(path.read_text())  # algo se escribió

    svc2 = TimerService(on_expire=lambda t: None, clock=clock, storage_path=path)
    restored = svc2.list()
    assert len(restored) == 1
    assert restored[0].id == t.id
    assert restored[0].label == "té"


def test_al_recargar_dispara_los_ya_vencidos(tmp_path):
    path = tmp_path / "timers.json"
    clock = FakeClock(1000.0)
    svc = TimerService(on_expire=lambda t: None, clock=clock, storage_path=path)
    svc.add_timer(60)  # vence en 1060

    clock.now = 2000.0
    fired = []
    TimerService(on_expire=fired.append, clock=clock, storage_path=path)
    assert len(fired) == 1
