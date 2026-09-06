import itertools

from asistente.audio.sink_sounddevice import SoundDeviceSink
from asistente.audio.source_sounddevice import SoundDeviceSource


class FakeStream:
    def __init__(self, **kw):
        self.kw = kw
        self.started = self.closed = False
        cb = kw["callback"]
        self._cb = cb

    def start(self):
        self.started = True
        # simula 3 bloques del micrófono
        for i in range(3):
            self._cb(bytes([i]) * (self.kw["blocksize"] * 2), self.kw["blocksize"], None, None)

    def stop(self):
        pass

    def close(self):
        self.closed = True


class FakeSD:
    RawInputStream = FakeStream

    def __init__(self):
        self.played = []

    def play(self, data, samplerate, device=None):
        self.played.append((bytes(data.tobytes()), samplerate))

    def wait(self):
        pass


def test_source_entrega_bloques_del_microfono():
    sd = FakeSD()
    src = SoundDeviceSource(sample_rate=16000, frame_ms=20, sd=sd)

    got = list(itertools.islice(src.frames(), 3))

    assert len(got) == 3
    assert all(len(b) == 640 for b in got)  # 20 ms @ 16 kHz s16le


def test_sink_reproduce_pcm_como_int16():
    sd = FakeSD()
    sink = SoundDeviceSink(sd=sd)

    sink.play(b"\x01\x00\x02\x00", sample_rate=22050)

    assert sd.played[0][1] == 22050
    assert sd.played[0][0] == b"\x01\x00\x02\x00"
