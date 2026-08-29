"""Fase 3c: rehace la boca con MuseTalk para mejorar la sincronia labial.

SadTalker genera el video entero; MuseTalk reconstruye solo la region labial
a partir del audio, y lo hace mejor. Se aplica encima del render, sin tocar
la voz ni el encuadre.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline_utils import ROOT, load_config, output_dir, resolve


def newest_video(carpeta):
    videos = sorted(Path(carpeta).rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
    return videos[-1] if videos else None


def run_musetalk(config, video, audio, destino):
    settings = config["lipsync"]
    repo = resolve(settings["musetalk_dir"])
    if not repo.is_dir():
        raise FileNotFoundError(
            f"No se encuentra MuseTalk en {repo}. Configura 'lipsync.musetalk_dir'")

    # MuseTalk lee las rutas desde un YAML y escribe dentro de su propio repo.
    trabajo = Path(tempfile.mkdtemp(prefix="lipsync_", dir=repo / "data"))
    entrada_v = trabajo / "entrada.mp4"
    entrada_a = trabajo / "entrada.wav"
    shutil.copy(video, entrada_v)
    shutil.copy(audio, entrada_a)

    yaml = trabajo / "tarea.yaml"
    yaml.write_text(
        f'task_0:\n video_path: "{entrada_v}"\n audio_path: "{entrada_a}"\n',
        encoding="utf-8")
    resultados = trabajo / "resultados"

    comando = [
        settings["python"], "-m", "scripts.inference",
        "--inference_config", str(yaml),
        "--result_dir", str(resultados),
        "--version", settings.get("version", "v15"),
        "--fps", str(config["video"].get("fps", 30)),
        # El valor por defecto de --unet_config apunta a la v1 aunque se pida v15.
        "--unet_config", settings["unet_config"],
        "--unet_model_path", settings["unet_model_path"],
    ]
    if settings.get("bbox_shift") is not None:
        comando += ["--bbox_shift", str(settings["bbox_shift"])]

    print("Rehaciendo la boca con MuseTalk...")
    subprocess.run(comando, check=True, cwd=repo, capture_output=True)

    salida = newest_video(resultados)
    if salida is None:
        raise RuntimeError(f"MuseTalk no genero video en {resultados}")
    shutil.copy(salida, destino)
    shutil.rmtree(trabajo, ignore_errors=True)
    return destino


def main():
    config = load_config()
    out = output_dir(config)

    video = out / "video.mp4"
    audio = out / "voice.wav"
    for fichero in (video, audio):
        if not fichero.exists():
            raise FileNotFoundError(f"Ejecuta antes las fases 2 y 3: falta {fichero}")

    destino = out / "video_lipsync.mp4"
    run_musetalk(config, video, audio, destino)

    meta_path = out / "script_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["lipsync"] = config["lipsync"].get("version", "v15")
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[3c] Boca rehecha -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
