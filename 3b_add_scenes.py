"""Fase 3b: sustituye parte del retrato por una escena generada, sin tocar la voz.

El avatar establece quien habla durante unos segundos y despues la imagen pasa a
una escena que ilustra lo que dice, mientras la voz clonada sigue por debajo.
La escena se deriva del propio texto: no hay que escribir el prompt a mano.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from pipeline_utils import ROOT, load_config, load_env, output_dir

PIDE_ESCENA = """Un video vertical acompaña a alguien que dice estas palabras:

{texto}

Escribe la descripción de UNA escena de video que ilustre ese sentimiento.

Reglas:
- Ambiente latinoamericano de pueblo: patio, cantina, camino, mar, calle al atardecer.
- NO describas personas famosas ni reconocibles. Gente anónima, o solo objetos y paisaje.
- Sin texto en pantalla, sin carteles, sin logotipos.
- Describe luz, encuadre y movimiento de cámara. Cámara suave y lenta.
- Entre 40 y 60 palabras, un solo párrafo.
- Devuelve solo la descripción."""


def media_duration(path):
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(salida.stdout.strip())


def scene_prompt(config, texto):
    """Deja que el modelo derive la escena del texto que se va a escuchar."""
    from google import genai
    import importlib.util as u

    spec = u.spec_from_file_location("fase1", ROOT / "1_generate_text.py")
    fase1 = u.module_from_spec(spec)
    spec.loader.exec_module(fase1)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return fase1.ask_gemini(client, config, PIDE_ESCENA.format(texto=texto)).strip()


def generate_scene(config, prompt, destino):
    """Genera el clip con Veo. Se cachea: repetir un prompt no se vuelve a pagar."""
    from google import genai
    from google.genai import types

    if destino.exists():
        print(f"Escena ya generada, se reutiliza: {destino.name}")
        return destino

    settings = config["escenas"]
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    operacion = client.models.generate_videos(
        model=settings["model"],
        source=types.GenerateVideosSource(prompt=prompt + " Formato vertical 9:16."),
        config=types.GenerateVideosConfig(aspect_ratio="9:16"),
    )
    print("Generando escena en Veo...")
    for _ in range(settings.get("timeout_checks", 60)):
        time.sleep(10)
        operacion = client.operations.get(operacion)
        if operacion.done:
            break

    respuesta = getattr(operacion, "response", None)
    if not (respuesta and respuesta.generated_videos):
        motivo = getattr(respuesta, "rai_media_filtered_reasons", None)
        raise RuntimeError(f"Veo no devolvio video. Filtrado: {motivo}")

    video = respuesta.generated_videos[0].video
    client.files.download(file=video)
    video.save(str(destino))
    destino.with_suffix(".json").write_text(
        json.dumps({"prompt": prompt, "modelo": settings["model"]},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    return destino


def scene_filter(config, overlay_path, restante):
    """Escala la escena al vertical del proyecto y le pone el mismo texto."""
    style = config["video"]["text"]
    cadena = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        f"fps={config['video'].get('fps', 30)}",
        # La escena dura 8 s; si el turno es mas largo se congela el ultimo frame.
        f"tpad=stop_mode=clone:stop_duration={max(0, restante):.0f}",
    ]
    if style.get("enabled", True) and overlay_path:
        cadena += [
            f"drawbox=x=0:y=ih*{style['scrim_top']}:w=iw:"
            f"h=ih*{1 - style['scrim_top']}:color=black@{style['scrim']}:t=fill",
            f"drawtext=fontfile={style['font']}:textfile='{overlay_path}':"
            f"fontsize={style['size']}:fontcolor=white:borderw={style['border']}:"
            f"bordercolor=black@0.9:line_spacing={style['line_spacing']}:"
            f"x=(w-text_w)/2:y=h*{style['verse_y']}",
        ]
    return ",".join(cadena)


def compose(config, avatar, voz, escena, overlay_path, destino, tmp):
    """Une los segundos de avatar con la escena y les pone la voz clonada encima."""
    total = media_duration(voz)
    corte = min(config["escenas"].get("corte_s", 4.0), total)
    resto = total - corte

    parte_a, parte_b = tmp / "_avatar.mp4", tmp / "_escena.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(avatar), "-t", f"{corte:.2f}",
                    "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(parte_a)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(escena),
                    "-vf", scene_filter(config, overlay_path, resto),
                    "-t", f"{resto:.2f}", "-an", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", str(parte_b)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(parte_a), "-i", str(parte_b),
                    "-i", str(voz), "-filter_complex",
                    "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
                    "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", str(destino)], check=True)

    print(f"Montaje: {corte:.1f}s de avatar + {resto:.1f}s de escena")
    if resto > config["escenas"].get("duracion_clip_s", 8):
        sobra = resto - config["escenas"].get("duracion_clip_s", 8)
        print(f"AVISO: {sobra:.1f}s con el fotograma congelado. Acorta el texto "
              f"o sube 'corte_s' para que la escena cubra menos.")


def main():
    import importlib.util as u

    load_env()
    config = load_config()
    out = output_dir(config)

    avatar = out / "video.mp4"
    voz = out / "voice.wav"
    meta_path = out / "script_meta.json"
    for fichero in (avatar, voz, meta_path):
        if not fichero.exists():
            raise FileNotFoundError(f"Ejecuta antes las fases 2 y 3: falta {fichero}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    texto = meta.get("verses", "")

    prompt = scene_prompt(config, texto)
    print(f"Escena derivada del texto:\n  {prompt}\n")

    ESCENAS = ROOT / config["escenas"].get("dir", "output/escenas")
    ESCENAS.mkdir(parents=True, exist_ok=True)
    clave = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:10]
    escena = generate_scene(config, prompt, ESCENAS / f"escena_{clave}.mp4")

    # El texto se redibuja sobre la escena con el mismo estilo del avatar.
    spec = u.spec_from_file_location("fase3", ROOT / "3_generate_video.py")
    fase3 = u.module_from_spec(spec)
    spec.loader.exec_module(fase3)
    overlay = None
    if texto and config["video"]["text"].get("enabled", True):
        overlay = out / "overlay_verse.txt"
        overlay.write_text(
            "\n".join(fase3.wrap_verses(texto, config["video"]["text"]["max_chars"])),
            encoding="utf-8")

    destino = out / "video_escena.mp4"
    compose(config, avatar, voz, escena, overlay, destino, out)

    meta["escena_prompt"] = prompt
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[3b] Video con escena -> {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
