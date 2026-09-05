"""Pone placas de serie a un capitulo: entrada con el titulo y cierre con CONTINUARA.

No usa GPU ni API: es solo FFmpeg, asi que no gasta cuota ni saldo.

    python serie_placas.py capitulo.mp4 --numero 1 --titulo "La horda"
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SERIE = "ALGO PASA EN SOATÁ"
FUENTE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def sonda(video, campo):
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", f"stream={campo}", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True)
    return salida.stdout.strip().split(",")[0]


def escapa(texto):
    """drawtext trata como sintaxis los dos puntos, comillas y barras."""
    return texto.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def placa(destino, ancho, alto, fps, segundos, lineas):
    """Genera un clip negro con texto centrado y audio en silencio."""
    filtros = []
    for i, (texto, tam, color, desplazamiento) in enumerate(lineas):
        filtros.append(
            f"drawtext=fontfile={FUENTE}:text='{escapa(texto)}':fontsize={tam}:"
            f"fontcolor={color}:x=(w-text_w)/2:y=(h-text_h)/2{desplazamiento}:"
            f"alpha='if(lt(t,0.4),t/0.4,if(gt(t,{segundos-0.4}),({segundos}-t)/0.4,1))'")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"color=c=black:s={ancho}x{alto}:d={segundos}:r={fps}",
         "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
         "-vf", ",".join(filtros), "-t", str(segundos),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(destino)],
        check=True)
    return destino


def vertical(entrada, destino, ancho=1080, alto=1920):
    """Encaja el apaisado en 9:16 sobre su propia imagen desenfocada."""
    vf = (f"split[fondo][frente];"
          f"[fondo]scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
          f"crop={ancho}:{alto},gblur=sigma=40[bg];"
          f"[frente]scale={ancho}:-2[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(entrada),
                    "-vf", vf, "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", str(destino)], check=True)
    return destino


def main():
    p = argparse.ArgumentParser(description="Placas de serie para un capitulo")
    p.add_argument("video")
    p.add_argument("--numero", type=int, required=True)
    p.add_argument("--titulo", required=True)
    p.add_argument("--salida", default=None)
    p.add_argument("--vertical", action="store_true", help="Ademas, version 9:16")
    args = p.parse_args()

    entrada = Path(args.video)
    if not entrada.exists():
        raise FileNotFoundError(entrada)

    ancho, alto = int(sonda(entrada, "width")), int(sonda(entrada, "height"))
    fps = sonda(entrada, "r_frame_rate").split("/")[0]
    base = ancho / 22          # el tamano de letra se adapta al video

    tmp = Path(tempfile.mkdtemp(prefix="placas_"))
    inicio = placa(tmp / "inicio.mp4", ancho, alto, fps, 2.5, [
        (SERIE, int(base), "white", "-60"),
        (f"Capítulo {args.numero}", int(base * 0.7), "0xD4AF37", "+30"),
        (args.titulo, int(base * 0.55), "white", "+90"),
    ])
    fin = placa(tmp / "fin.mp4", ancho, alto, fps, 2.0, [
        ("CONTINUARÁ", int(base * 0.9), "white", "+0"),
    ])

    salida = Path(args.salida) if args.salida else entrada.with_name(
        f"{entrada.stem}_cap{args.numero}.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-i", str(inicio), "-i", str(entrada), "-i", str(fin),
                    "-filter_complex",
                    "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]",
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(salida)],
                   check=True)
    print(f"con placas -> {salida}")

    if args.vertical:
        v = salida.with_name(f"{salida.stem}_vertical.mp4")
        vertical(salida, v)
        print(f"vertical   -> {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
