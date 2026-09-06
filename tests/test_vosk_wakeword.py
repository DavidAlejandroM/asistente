from asistente.wakeword.vosk_wakeword import VoskWakeWord

FRAME = b"\x00\x00" * 320


class FakeRec:
    """Recognizer de Vosk falso: recorre un guion de (es_final, texto)."""

    def __init__(self, script):
        self._script = list(script)
        self._cur = (False, "")
        self.resets = 0

    def AcceptWaveform(self, frame):
        self._cur = self._script.pop(0) if self._script else (False, "")
        return self._cur[0]

    def Result(self):
        import json
        return json.dumps({"text": self._cur[1]})

    def PartialResult(self):
        import json
        return json.dumps({"partial": self._cur[1]})

    def Reset(self):
        self.resets += 1


def _det(script, **kw):
    return VoskWakeWord(
        phrases=["hey paco"], recognizer=FakeRec(script), cooldown_frames=3, **kw
    )


def test_dispara_con_resultado_final_que_contiene_la_frase():
    det = _det([(False, "hey"), (True, "hey paco")])
    assert det.detect(FRAME) is False
    assert det.detect(FRAME) is True


def test_dispara_con_resultado_parcial_sin_esperar_al_silencio():
    det = _det([(False, "hey"), (False, "hey paco")])
    assert det.detect(FRAME) is False
    assert det.detect(FRAME) is True


def test_no_dispara_con_ruido_o_unk():
    det = _det([(True, "[unk]"), (True, ""), (False, "hola qué tal")])
    assert [det.detect(FRAME) for _ in range(3)] == [False, False, False]


def test_cooldown_tras_disparo():
    det = _det([(True, "hey paco")] + [(False, "hey paco")] * 5)
    assert det.detect(FRAME) is True
    assert [det.detect(FRAME) for _ in range(3)] == [False, False, False]
    assert det.detect(FRAME) is True


def test_reset_propaga_al_recognizer():
    det = _det([(False, "")])
    det.reset()
    assert det._rec.resets >= 1
