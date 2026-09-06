from asistente.skills.timers import TimerService, TimerSkill


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


def _skill(tz="UTC"):
    clock = FakeClock(1000.0)
    svc = TimerService(on_expire=lambda t: None, clock=clock, tz=tz)
    return TimerSkill(svc, clock=clock), svc, clock


def test_set_timer_crea_y_confirma_en_lenguaje_natural():
    skill, svc, _ = _skill()
    out = skill.run({"action": "set_timer", "seconds": 600, "label": "pasta"})
    assert "pasta" in out and "10 minutos" in out
    assert len(svc.list()) == 1


def test_set_timer_sin_duracion_pregunta():
    skill, svc, _ = _skill()
    out = skill.run({"action": "set_timer"})
    assert "?" in out
    assert svc.list() == []


def test_list_muestra_lo_que_falta():
    skill, svc, clock = _skill()
    skill.run({"action": "set_timer", "seconds": 120})
    clock.now = 1060
    out = skill.run({"action": "list"})
    assert "1 minuto" in out


def test_cancel_por_id():
    skill, svc, _ = _skill()
    skill.run({"action": "set_timer", "seconds": 60})
    tid = svc.list()[0].id
    assert "Cancelado" in skill.run({"action": "cancel", "id": tid})
    assert svc.list() == []


def test_cancel_id_inexistente():
    skill, _, _ = _skill()
    assert "No encuentro" in skill.run({"action": "cancel", "id": "zzz"})


def test_metadata():
    skill, _, _ = _skill()
    assert skill.name == "manage_timers"
    assert "action" in skill.parameters["required"]
