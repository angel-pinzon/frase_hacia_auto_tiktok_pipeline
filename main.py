"""Orquestador: ejecuta las cuatro fases del pipeline en orden."""

import subprocess
import sys
from pathlib import Path

from pipeline_utils import active_character, load_config

ROOT = Path(__file__).resolve().parent
PHASES = [
    "1_generate_text.py",
    "2_generate_voice.py",
    "3_generate_video.py",
    "4_upload_tiktok.py",
]


def main():
    config = load_config()
    print(f"Personaje activo: {active_character(config)['name']}\n")

    for phase in PHASES:
        result = subprocess.run([sys.executable, phase], cwd=ROOT)
        if result.returncode != 0:
            print(f"\nEl pipeline se detuvo en {phase}", file=sys.stderr)
            return result.returncode

    print("\nPipeline completado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
