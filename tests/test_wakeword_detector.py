from asistente.wakeword.openwakeword_detector import OpenWakeWordDetector

FRAME = b"\x00\x00" * 320


class FakeModel:
    def __init__(self, scores):
        self._scores = list(scores)
        self.reset_calls = 0

    def predict(self, samples):
        s = self._scores.pop(0) if self._scores else 0.0
        return {"hey_jarvis": s}

    def reset(self):
        self.reset_calls += 1


def _det(scores, **kw):
    return OpenWakeWordDetector(
        model="hey_jarvis", threshold=0.5, model_impl=FakeModel(scores),
        cooldown_frames=3, **kw,
    )


def test_dispara_al_superar_el_umbral():
    det = _det([0.1, 0.2, 0.9])
    assert det.detect(FRAME) is False
    assert det.detect(FRAME) is False
    assert det.detect(FRAME) is True


def test_cooldown_evita_disparos_repetidos():
    det = _det([0.9, 0.95, 0.95, 0.95, 0.9])
    assert det.detect(FRAME) is True            # frame 0
    assert det.detect(FRAME) is False           # en cooldown
    assert det.detect(FRAME) is False           # en cooldown
    assert det.detect(FRAME) is False           # último frame de cooldown
    assert det.detect(FRAME) is True            # ya puede volver a disparar


def test_reset_propaga_al_modelo():
    det = _det([0.0])
    det.reset()
    assert det._model.reset_calls == 1


class PathModel:
    """Simula openWakeWord con un modelo custom: la clave es el nombre del archivo."""

    def predict(self, samples):
        return {"oye_asistente": 0.9}

    def reset(self):
        pass


def test_modelo_custom_por_ruta_usa_el_nombre_del_archivo_como_clave():
    det = OpenWakeWordDetector(
        model="/home/pi/asistente/models/oye_asistente.tflite",
        threshold=0.5,
        model_impl=PathModel(),
    )
    assert det.detect(FRAME) is True
