from asistente.fakes import (
    FakeAudioSink,
    FakeAudioSource,
    FakeRecorder,
    FakeSTT,
    FakeTTS,
    FakeWakeWord,
)
from asistente.orchestrator import Orchestrator, State


class FakeBrain:
    def __init__(self, reply="respuesta"):
        self.reply = reply
        self.seen = []

    def process(self, text):
        self.seen.append(text)
        return self.reply


def build(source_frames, *, stt="qué hora es", brain=None, **kw):
    brain = brain or FakeBrain("son las tres")
    tts = FakeTTS(sample_rate=16000)
    sink = FakeAudioSink()
    orch = Orchestrator(
        audio_source=FakeAudioSource(source_frames),
        wakeword=FakeWakeWord(b"WAKE"),
        recorder=FakeRecorder(b"AUDIO"),
        stt=FakeSTT(stt),
        brain=brain,
        tts=tts,
        sink=sink,
        sample_rate=16000,
        **kw,
    )
    return orch, brain, tts, sink


def test_ciclo_completo_de_wake_a_voz():
    orch, brain, tts, sink = build([b"ruido", b"WAKE", b"resto"])

    orch.run_once()

    assert brain.seen == ["qué hora es"]
    assert tts.spoken == ["son las tres"]
    assert sink.played == [(b"son las tres", 16000)]


def test_transcripcion_vacia_no_invoca_al_cerebro_y_avisa():
    orch, brain, tts, sink = build([b"WAKE", b"x"], stt="   ")

    orch.run_once()

    assert brain.seen == []
    assert tts.spoken and "entend" in tts.spoken[0].lower()
    assert len(sink.played) == 1


def test_estado_queda_disponible_para_la_ui():
    orch, brain, tts, sink = build([b"WAKE", b"x"])
    assert orch.status().state == State.IDLE

    orch.run_once()

    st = orch.status()
    assert st.last_transcript == "qué hora es"
    assert st.last_response == "son las tres"
    assert st.state == State.IDLE


def test_frase_de_activacion_se_reproduce_antes_de_escuchar():
    orch, brain, tts, sink = build([b"WAKE", b"x"], wake_response="dime")

    orch.run_once()

    assert tts.spoken[0] == "dime"
    assert tts.spoken[1] == "son las tres"


def test_run_once_devuelve_false_si_el_audio_se_agota_sin_wake():
    orch, brain, tts, sink = build([b"a", b"b", b"c"])

    assert orch.run_once() is False
    assert brain.seen == []
