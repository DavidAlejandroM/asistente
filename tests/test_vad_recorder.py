from asistente.audio.vad import VadRecorder

FRAME = 640  # 20 ms @ 16 kHz s16le


def frames_from(pattern_len):
    """Frames identificables: el frame i tiene todos sus bytes == i % 256."""
    return (bytes([i % 256]) * FRAME for i in range(pattern_len))


class FakeVad:
    def __init__(self, speech_flags):
        self._flags = list(speech_flags)

    def is_speech(self, frame: bytes) -> bool:
        idx = frame[0]
        return self._flags[idx] if idx < len(self._flags) else False


def indices(pcm: bytes) -> list[int]:
    return [pcm[i] for i in range(0, len(pcm), FRAME)]


def _rec(**kw):
    defaults = dict(
        sample_rate=16000, frame_ms=20, start_frames=2, silence_ms=60,
        preroll_ms=40, max_duration_s=1.0, max_wait_s=1.0, min_utterance_ms=0,
        min_rms=0.0,
    )
    defaults.update(kw)
    return VadRecorder(**defaults)


def test_captura_desde_preroll_hasta_el_silencio_final():
    # frames 0-1 silencio, 2-6 voz, 7+ silencio
    flags = [False, False, True, True, True, True, True, False, False, False, False]
    rec = _rec(vad=FakeVad(flags))

    pcm = rec.record(frames_from(20))

    got = indices(pcm)
    assert got[0] == 0 and 1 in got  # incluye los 2 frames de preroll (40 ms)
    assert 2 in got and 6 in got  # toda la voz
    # se corta tras 3 frames de silencio (silence_ms=60 / 20)
    assert max(got) <= 9


def test_para_en_max_duration():
    flags = [True] * 300
    rec = _rec(vad=FakeVad(flags), max_duration_s=0.1)  # 5 frames

    pcm = rec.record(frames_from(100))

    assert len(indices(pcm)) <= 6


def test_devuelve_vacio_si_nunca_hay_voz():
    flags = [False] * 300
    rec = _rec(vad=FakeVad(flags), max_wait_s=0.1)  # 5 frames

    pcm = rec.record(frames_from(100))

    assert pcm == b""


def test_descarta_rafagas_de_ruido_demasiado_cortas():
    # 3 frames de "voz" (60 ms) rodeados de silencio; min_utterance_ms=200
    flags = [False, True, True, True, False, False, False, False]
    rec = _rec(vad=FakeVad(flags), min_utterance_ms=200)

    assert rec.record(frames_from(20)) == b""


def test_descarta_locucion_con_nivel_rms_bajo():
    flags = [False] + [True] * 15 + [False] * 4
    rec = _rec(vad=FakeVad(flags), min_utterance_ms=0, min_rms=5000.0)

    # frames_from genera niveles moderados (<5000 rms) -> se descarta
    assert rec.record(frames_from(25)) == b""


def test_reframe_trocea_chunks_de_tamano_irregular():
    flags = [False, True, True, True, True, False, False, False]
    rec = _rec(vad=FakeVad(flags))

    # un solo chunk gigante con 8 frames pegados
    big = b"".join(bytes([i]) * FRAME for i in range(8))
    pcm = rec.record(iter([big]))

    assert 1 in indices(pcm) and 4 in indices(pcm)
