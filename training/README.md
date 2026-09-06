# Palabra de activación en español

openWakeWord no trae modelos en español, pero se entrena uno propio con **voz
sintética** (no hace falta grabar nada). El modelo resultante es un `.tflite` de
~1 MB que corre de sobra en la Pi Zero 2 W.

## Dónde entrenar

**No en la Pi ni en un portátil normal.** El entrenamiento necesita GPU y descarga
varios GB de datos negativos. Opciones:

- **Google Colab** (gratis, con GPU) — lo más fácil.
- Tu PC si tiene GPU NVIDIA.

El *uso* del modelo ya entrenado sí va en la Pi, sin problema.

## Pasos (en Colab)

```python
!pip install -q openwakeword
!git clone https://github.com/rhasspy/piper-sample-generator
!git clone <este-repo> asistente
%cd asistente
!python training/train_wakeword.py --config training/wakeword.yaml
```

Edita antes `training/wakeword.yaml`:

- `target_phrase`: lo que dirás para activarlo (`"oye asistente"`, `"hola casa"`, …).
  Evita frases de 1 sílaba o palabras muy comunes (más falsos positivos).
- `model_name`: nombre del archivo de salida.
- `n_samples`: 30 000 va bien; menos entrena más rápido pero reconoce peor.

Salida: `out/oye_asistente.tflite`.

## Instalar en la Pi

```bash
mkdir -p ~/asistente/models
scp out/oye_asistente.tflite pi@raspberry:~/asistente/models/
```

`config.yaml`:

```yaml
wakeword:
  provider: openwakeword
  model: /home/pi/asistente/models/oye_asistente.tflite
  threshold: 0.5      # sube si hay falsos positivos, baja si no te oye
  framework: tflite
```

Reinicia el asistente. Ajusta `threshold` desde la UI de administración probando.

## Alternativa rápida sin entrenar

Usar un modelo incorporado (`hey_jarvis`, `alexa`, `hey_mycroft`). Funciona ya, solo
que la palabra es en inglés.
