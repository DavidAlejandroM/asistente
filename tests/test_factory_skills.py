import textwrap

from asistente.config import load_config
from asistente.factory import build_skills


def _cfg(tmp_path, extra=""):
    p = tmp_path / "config.yaml"
    p.write_text(
        textwrap.dedent(
            """
            llm: {provider: fake}
            stt: {provider: fake}
            tts: {provider: fake}
            wakeword: {provider: fake}
            """
        )
        + textwrap.dedent(extra)
    )
    return load_config(p)


def test_weather_se_registra_si_hay_ubicacion(tmp_path):
    cfg = _cfg(tmp_path, "location: {lat: 6.28, lon: -75.33, name: SV}\n")
    reg = build_skills(cfg)
    assert "get_weather" in reg.all_names()
    assert reg.is_enabled("get_weather")


def test_weather_no_se_registra_sin_ubicacion(tmp_path):
    reg = build_skills(_cfg(tmp_path))
    assert "get_weather" not in reg.all_names()


def test_disabled_skills_desactiva_pero_registra(tmp_path):
    cfg = _cfg(
        tmp_path,
        """
        location: {lat: 6.28, lon: -75.33}
        disabled_skills: [get_weather]
        """,
    )
    reg = build_skills(cfg)
    assert "get_weather" in reg.all_names()
    assert not reg.is_enabled("get_weather")
    assert "get_weather" not in [t.name for t in reg.tool_specs()]
