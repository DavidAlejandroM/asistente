import textwrap

import pytest

from asistente.config import AppConfig, load_config


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(text))
    return p


def test_carga_config_minima_con_defaults(tmp_path):
    path = _write(
        tmp_path,
        """
        llm:
          provider: ollama
          url: http://pc:11434
          model: qwen2.5:7b
        stt:
          provider: faster_whisper_http
          url: http://pc:8001
        tts:
          provider: piper_http
          url: http://pc:8002
        wakeword:
          provider: openwakeword
        """,
    )
    cfg = load_config(path)

    assert isinstance(cfg, AppConfig)
    assert cfg.llm.provider == "ollama"
    assert cfg.llm.settings["model"] == "qwen2.5:7b"
    assert cfg.admin.enabled is True
    assert cfg.admin.port == 8080


def test_falla_si_falta_una_seccion_obligatoria(tmp_path):
    path = _write(
        tmp_path,
        """
        llm:
          provider: ollama
        stt:
          provider: faster_whisper_http
        tts:
          provider: piper_http
        """,
    )
    with pytest.raises(ValueError):
        load_config(path)


def test_config_de_skills_y_location_se_conservan(tmp_path):
    path = _write(
        tmp_path,
        """
        llm: {provider: ollama}
        stt: {provider: faster_whisper_http}
        tts: {provider: piper_http}
        wakeword: {provider: openwakeword}
        location: {lat: 40.4, lon: -3.7, name: Madrid}
        skills:
          home_assistant:
            url: http://ha:8123
          spotify:
            device_name: asistente
        """,
    )
    cfg = load_config(path)

    assert cfg.location.lat == 40.4
    assert cfg.location.name == "Madrid"
    assert cfg.skills["home_assistant"]["url"] == "http://ha:8123"
