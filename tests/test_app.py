import io
import textwrap

from asistente.app import run_text
from asistente.config import load_config


def _cfg(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text(
        textwrap.dedent(
            """
            llm: {provider: fake}
            stt: {provider: fake}
            tts: {provider: fake}
            wakeword: {provider: fake}
            audio: {source: fake, sink: fake, recorder: fake}
            """
        )
    )
    return load_config(p)


def test_run_text_procesa_lineas_de_stdin_y_escribe_respuestas(tmp_path):
    cfg = _cfg(tmp_path)
    stdin = io.StringIO("hola\nadiós\n")
    stdout = io.StringIO()

    run_text(cfg, stdin=stdin, stdout=stdout)

    salida = stdout.getvalue()
    assert "has dicho: hola" in salida
    assert "has dicho: adiós" in salida
