from asistente.audio.wavutil import pcm_to_wav, wav_to_pcm


def test_roundtrip_pcm_wav_pcm():
    pcm = bytes(range(256)) * 4  # 1024 bytes = 512 muestras s16le
    wav = pcm_to_wav(pcm, sample_rate=16000)

    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"

    out_pcm, rate = wav_to_pcm(wav)
    assert rate == 16000
    assert out_pcm == pcm


def test_wav_to_pcm_lee_cabecera_de_44_bytes():
    pcm = b"\x01\x02" * 100
    wav = pcm_to_wav(pcm, sample_rate=22050)
    out_pcm, rate = wav_to_pcm(wav)
    assert rate == 22050
    assert out_pcm == pcm
