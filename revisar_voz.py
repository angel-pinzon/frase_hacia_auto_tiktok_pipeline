"""Comprueba una voz generada: que se entiende entera y donde respira.

Transcribe el audio completo y luego lo corta por la mitad de cada silencio
y transcribe cada trozo por separado. Asi se ve exactamente que frase queda
entre pausa y pausa, y cuanto dura cada pausa.

Hace falta hacerlo asi porque las marcas de tiempo por palabra de Whisper no
sirven para medir pausas: estiran el final de cada palabra sobre el silencio
y dan 0,00 s donde en realidad hay medio segundo.

Usa Whisper, que esta instalado en el entorno de OmniVoice:

    ~/omni_voice_project/venv/bin/python revisar_voz.py output/DiomedesDiaz/voice.wav
    ~/omni_voice_project/venv/bin/python revisar_voz.py voice.wav --desde 8

Salida de ejemplo:

    [ 7.76- 9.61] Tus amistades, llegamos aqui...   <- pausa 0.68s
    [ 9.61-10.96] para compartir                    <- pausa 0.50s

Un aviso: en trozos de menos de medio segundo Whisper a veces se inventa una
palabra ("Gracias."). Si aparece en un fragmento minusculo, no esta en el audio.
"""

import argparse
import logging
import re
import subprocess
import tempfile
import warnings
from pathlib import Path

MODELO = "openai/whisper-large-v3-turbo"


def duracion(audio):
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)],
        capture_output=True, text=True, check=True)
    return float(salida.stdout)


def silencios(audio, ruido_db, minimo_s):
    salida = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(audio),
         "-af", f"silencedetect=noise={ruido_db}dB:d={minimo_s}", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    inicios = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", salida)]
    finales = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", salida)]
    return list(zip(inicios, finales))


def main():
    p = argparse.ArgumentParser(description="Transcribe una voz y mide sus pausas")
    p.add_argument("audio")
    p.add_argument("--desde", type=float, default=0.0,
                   help="Revisar solo a partir de este segundo")
    p.add_argument("--pausa-minima", type=float, default=0.15,
                   help="Silencios mas cortos no cuentan como pausa (s)")
    p.add_argument("--ruido", type=float, default=-32, help="Umbral de silencio en dB")
    args = p.parse_args()

    warnings.filterwarnings("ignore")
    logging.getLogger("transformers").setLevel(logging.ERROR)
    from transformers import pipeline
    asr = pipeline("automatic-speech-recognition", model=MODELO, device=0)
    habla = {"language": "spanish"}

    audio = Path(args.audio)
    total = duracion(audio)
    print(f"  duracion: {total:.2f}s")
    print(f"  TODO: {asr(str(audio), generate_kwargs=habla)['text'].strip()}")

    # los silencios pegados al final son la cola del audio, no pausas
    pausas = [(a, b) for a, b in silencios(audio, args.ruido, args.pausa_minima)
              if args.desde < a < total - 0.3]
    bordes = [args.desde] + [(a + b) / 2 for a, b in pausas] + [total]

    with tempfile.TemporaryDirectory(prefix="revisar_voz_") as tmp:
        for i in range(len(bordes) - 1):
            t0, t1 = bordes[i], bordes[i + 1]
            trozo = Path(tmp) / f"trozo_{i}.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t0), "-to", str(t1),
                            "-i", str(audio), str(trozo)], check=True)
            texto = asr(str(trozo), generate_kwargs=habla)["text"].strip()
            nota = f"   <- pausa {pausas[i][1] - pausas[i][0]:.2f}s" if i < len(pausas) else ""
            print(f"  [{t0:5.2f}-{t1:5.2f}] {texto}{nota}")


if __name__ == "__main__":
    main()
