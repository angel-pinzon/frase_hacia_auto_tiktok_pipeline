"""Fase 3: anima el avatar con SadTalker y empaqueta el resultado en vertical 9:16."""

import json
import subprocess
import sys

from pipeline_utils import active_character, load_config, output_dir, resolve


def run_sadtalker(config, character, audio_path, result_dir):
    settings = config["video"]
    if not settings.get("sadtalker_dir"):
        raise RuntimeError(
            "Configura 'video.sadtalker_dir' en config.json con la ruta del repo de SadTalker"
        )

    sadtalker_dir = resolve(settings["sadtalker_dir"])
    image_path = resolve(character["image_path"])
    if not image_path.exists():
        raise FileNotFoundError(f"No se encuentra el avatar: {image_path}")

    # Con imagenes muy grandes el detector de puntos faciales falla al recortar.
    largo = settings.get("max_source", 1600)
    ancho, alto = video_size(image_path)
    if max(ancho, alto) > largo:
        reducida = result_dir / "avatar_reducido.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(image_path),
             "-vf", f"scale='if(gt(iw,ih),{largo},-2)':'if(gt(iw,ih),-2,{largo})'",
             "-q:v", "2", str(reducida)],
            check=True,
        )
        print(f"Avatar reducido de {ancho}x{alto} a {largo} px de lado mayor")
        image_path = reducida

    command = [
        settings["python"],
        "inference.py",
        "--driven_audio", str(audio_path),
        "--source_image", str(image_path),
        "--result_dir", str(result_dir),
        "--preprocess", settings.get("preprocess", "full"),
        "--size", str(settings.get("size", 256)),
        "--expression_scale", str(settings.get("expression_scale", 1.0)),
        "--pose_style", str(settings.get("pose_style", 0)),
    ]
    # 'still' congela la cabeza: quitarlo da movimiento y mucho mas realismo.
    if settings.get("still", True):
        command.append("--still")
    if settings.get("enhancer"):
        command += ["--enhancer", settings["enhancer"]]
    subprocess.run(command, check=True, cwd=sadtalker_dir)

    renders = sorted(result_dir.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if not renders:
        raise RuntimeError(f"SadTalker no genero ningun video en {result_dir}")
    return renders[-1]


DETECT = """
import cv2, json, sys
img = cv2.imread(sys.argv[1])
caja = None

# RetinaFace aguanta caras giradas, sombreros y sombras; Haar no.
try:
    import torch
    from facexlib.detection import init_detection_model
    net = init_detection_model('retinaface_resnet50', half=False, device='cuda')
    with torch.no_grad():
        caras = net.detect_faces(img, 0.9)
    if len(caras):
        x1, y1, x2, y2 = max(caras, key=lambda f: (f[2] - f[0]) * (f[3] - f[1]))[:4]
        caja = [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]
except Exception:
    pass

if caja is None:
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    caras = cascade.detectMultiScale(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(80, 80))
    if len(caras):
        caja = [int(v) for v in max(caras, key=lambda f: f[2] * f[3])]

print(json.dumps(caja))
"""


def detect_face(config, image_path):
    """Devuelve (x, y, w, h) de la cara mas grande, o None si no la encuentra."""
    result = subprocess.run(
        [config["video"]["python"], "-c", DETECT, str(image_path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout.strip().splitlines()[-1])


def crop_filter(face, source_size, width, height):
    """Franja 9:16 a maxima resolucion, centrada horizontalmente en la cara."""
    src_w, src_h = source_size
    crop_w = min(src_w, round(src_h * width / height))
    crop_h = min(src_h, round(crop_w * height / width))

    face_cx = face[0] + face[2] // 2
    x = max(0, min(src_w - crop_w, face_cx - crop_w // 2))
    return f"crop={crop_w}:{crop_h}:{x}:0,scale={width}:{height},setsar=1"


def first_frame(video, destination):
    """SadTalker reescala segun --size, asi que la cara se busca en el render."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vframes", "1", str(destination)],
        check=True,
    )
    return destination


def video_size(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
         "-of", "csv=p=0:s=x", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip().split("\n")[0]
    return tuple(int(v) for v in out.split("x")[:2])


def wrap_verses(verses, max_chars):
    """Respeta el corte de verso original y parte solo las lineas muy largas."""
    lines = []
    for raw in verses.splitlines():
        current = ""
        for word in raw.split():
            if current and len(current) + 1 + len(word) > max_chars:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)
    return lines


def text_filters(settings, meta, out_dir):
    """Capa de texto: oscurecido inferior, versos y titulo de la cancion."""
    style = settings.get("text", {})
    if not style.get("enabled", True) or not meta.get("verses"):
        return []

    size = style.get("size", 46)
    lines = wrap_verses(meta["verses"], style.get("max_chars", 30))
    verse_file = out_dir / "overlay_verse.txt"
    verse_file.write_text("\n".join(lines), encoding="utf-8")

    font = style.get("font", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    common = f"fontfile={font}:borderw={style.get('border', 4)}:bordercolor=black@0.9"

    filters = [
        f"drawbox=x=0:y=ih*{style.get('scrim_top', 0.55)}:w=iw:"
        f"h=ih*{1 - style.get('scrim_top', 0.55)}:color=black@{style.get('scrim', 0.5)}:t=fill",
        f"drawtext={common}:textfile='{verse_file}':fontsize={size}:fontcolor=white:"
        f"line_spacing={style.get('line_spacing', 14)}:x=(w-text_w)/2:"
        f"y=h*{style.get('verse_y', 0.62)}",
    ]

    if meta.get("song"):
        title = meta["song"].upper().replace("'", "").replace(":", "")
        filters.append(
            f"drawtext={common}:text='{title}':fontsize={int(size * 0.55)}:"
            f"fontcolor={style.get('title_color', 'gold')}:x=(w-text_w)/2:y=h-{style.get('title_margin', 130)}"
        )
    return filters


def to_vertical(config, source, destination, face=None, meta=None):
    settings = config["video"]
    width, height = settings["width"], settings["height"]

    if face and settings.get("crop_to_face", True):
        chain = [crop_filter(face, video_size(source), width, height)]
    else:
        chain = [
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        ]

    chain += text_filters(settings, meta or {}, destination.parent)
    video_filter = ",".join(chain)
    command = [
        "ffmpeg", "-y",
        "-i", str(source),
        "-vf", video_filter,
        "-r", str(settings["fps"]),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(destination),
    ]
    subprocess.run(command, check=True)


def main():
    config = load_config()
    out = output_dir(config)

    audio_path = out / "voice.wav"
    if not audio_path.exists():
        raise FileNotFoundError(f"Ejecuta primero la fase 2: falta {audio_path}")

    result_dir = out / "sadtalker"
    result_dir.mkdir(parents=True, exist_ok=True)

    character = active_character(config)
    render = run_sadtalker(config, character, audio_path, result_dir)

    face = detect_face(config, first_frame(render, result_dir / "frame.png"))
    print(f"Cara detectada en {face}" if face else "AVISO: sin cara detectada, se usan barras")

    meta_path = out / "script_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    destination = out / "video.mp4"
    to_vertical(config, render, destination, face, meta)

    print(f"[3/4] Video vertical generado -> {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
