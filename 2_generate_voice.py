"""Fase 2: sintetiza el guion con la voz clonada del personaje activo (OmniVoice)."""

import json
import struct
import subprocess
import sys
import wave

from pipeline_utils import active_character, load_config, output_dir, resolve

FRAME = 0.025     # ventana de analisis en segundos
SILENCIO = 50     # RMS por debajo del cual se considera silencio


def tail_level(path):
    """Energia con la que termina el audio: alta = OmniVoice corto en seco."""
    with wave.open(str(path), "rb") as wav:
        frames, rate = wav.getnframes(), wav.getframerate()
        samples = struct.unpack(f"<{frames}h", wav.readframes(frames))

    window = int(rate * FRAME)
    envelope = []
    for i in range(0, frames, window):
        chunk = samples[i:i + window]
        if chunk:
            envelope.append((sum(x * x for x in chunk) / len(chunk)) ** 0.5)

    return next((v for v in reversed(envelope) if v > SILENCIO), 0.0)


RITMO = """
import json, sys, warnings, logging
warnings.filterwarnings('ignore'); logging.getLogger('transformers').setLevel(logging.ERROR)
from transformers import pipeline
asr = pipeline('automatic-speech-recognition', model='openai/whisper-large-v3-turbo', device=0)
r = asr(sys.argv[1], generate_kwargs={'language': 'spanish'}, return_timestamps='word')
peor = None
for c in r['chunks']:
    inicio, fin = c['timestamp']
    palabra = c['text'].strip(' ,.;:!?')
    if fin is None or len(palabra) <= 3:
        continue
    dur = fin - inicio
    if peor is None or dur < peor[1]:
        peor = (palabra, dur)
print(json.dumps(peor))
"""


def rushed_word(config, path):
    """Palabra mas comprimida del audio: OmniVoice a veces se come silabas."""
    settings = config["omnivoice"]
    result = subprocess.run(
        [settings["python"], "-c", RITMO, str(path)],
        capture_output=True, text=True, cwd=settings.get("cwd") or None,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return None


def build_command(config, character, script_text, destination):
    settings = config["omnivoice"]
    ref_audio = resolve(character["audio_path"])
    if not ref_audio.exists():
        raise FileNotFoundError(f"No se encuentra el audio de referencia: {ref_audio}")

    # OmniVoice recorta el final de la ultima palabra: la coletilla absorbe el corte.
    # Cada personaje tiene la suya; si no, se usa la global.
    suffix = character.get("text_suffix", settings.get("text_suffix", ""))
    placeholders = {
        "ref_audio": str(ref_audio),
        "ref_text": character["audio_text"],
        "gen_text": script_text + suffix,
        "output": str(destination),
    }
    args = [arg.format(**placeholders) for arg in settings["args"]]
    if settings.get("speed"):
        args += ["--speed", str(settings["speed"])]
    return [settings["python"], "-m", settings["module"], *args]


def main():
    config = load_config()
    out = output_dir(config)

    script_path = out / "script.txt"
    if not script_path.exists():
        raise FileNotFoundError(f"Ejecuta primero la fase 1: falta {script_path}")
    script_text = script_path.read_text(encoding="utf-8").strip()

    settings = config["omnivoice"]
    destination = out / "voice.wav"
    command = build_command(config, active_character(config), script_text, destination)
    limit = settings.get("cut_threshold", 250)

    min_dur = settings.get("min_word_duration", 0.13)

    # Los dos defectos de OmniVoice son aleatorios: se regenera hasta que salga limpio.
    for attempt in range(1, settings.get("max_attempts", 3) + 1):
        subprocess.run(command, check=True, cwd=settings.get("cwd") or None)
        if not destination.exists():
            raise RuntimeError(f"OmniVoice no genero el audio esperado en {destination}")

        level = tail_level(destination)
        if level > limit:
            print(f"Intento {attempt}: final cortado (nivel {level:.0f}), regenerando")
            continue

        peor = rushed_word(config, destination) if min_dur else None
        if peor and peor[1] < min_dur:
            print(f"Intento {attempt}: '{peor[0]}' atropellada ({peor[1]:.2f}s), regenerando")
            continue

        detalle = f", palabra mas corta '{peor[0]}' {peor[1]:.2f}s" if peor else ""
        print(f"Audio limpio (final {level:.0f}{detalle})")
        break
    else:
        print("AVISO: se agotaron los intentos, el audio conserva algun defecto")

    print(f"[2/4] Voz generada -> {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
