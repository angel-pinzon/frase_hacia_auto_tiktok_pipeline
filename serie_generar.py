"""Genera los actos de un capitulo de la serie a partir de su ficha.

Lee un JSON de prompts/escenas/, genera cada acto con Veo encadenandolo
desde el ultimo fotograma del anterior, y los une en una secuencia. Las
placas y las correcciones van despues, con serie_placas.py.

    python serie_generar.py prompts/escenas/cap6_los-que-vuelven.json
    python serie_generar.py prompts/escenas/cap4_lo-que-buscaban.json --solo-acto 3
    python serie_generar.py prompts/escenas/cap8_el-amanecer.json --solo-acto 2 --entrada fotograma.jpg

Gasta cuota: una generacion por acto. El plan Tier 1 da 10 al dia.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pipeline_utils import load_env

ROOT = Path(__file__).resolve().parent
ESCENAS = ROOT / "output" / "escenas"

# Veo admite 2 peticiones por minuto; entre acto y acto se espera un poco
# mas de la mitad de ese minuto.
PAUSA_ENTRE_ACTOS = 35

# Brillo medio minimo del fotograma desde el que se encadena el acto
# siguiente. Por debajo, el modelo no ve la arquitectura y la reinventa desde
# el texto: en el capitulo 6 un acto que terminaba a oscuras -brillo 17- hizo
# que el siguiente saliera con otra iglesia y una cupula azul maciza, cuando
# la real es blanca con franjas. La serie vive de que el sitio se reconozca,
# asi que antes de gastar una generacion en una cadena perdida, se para.
BRILLO_MINIMO_ENCADENADO = 28


def prompt_completo(ficha, acto):
    """El texto del acto mas lo que se repite en todos: sitio, luz y reglas.

    La arquitectura va copiada en cada acto porque es lo que evita que el
    modelo se invente edificios al encadenar. Las notas de la ficha -nota,
    riesgo, revision...- son para quien la lee y nunca llegan al modelo.
    """
    # un acto puede traer su propia arquitectura o texto comun, cuando cambia
    # de encuadre a mitad de capitulo -del plano aereo a la plaza, por ejemplo-
    partes = [acto["prompt"], acto.get("arquitectura", ficha["arquitectura"])]
    luz = acto.get("luz_prompt", ficha.get("luz_prompt"))
    if luz:
        partes.append(luz)
    partes.append(acto.get("comun", ficha["comun"]))
    return " ".join(partes)


def genera(cliente, modelo, prompt, imagen, destino):
    from google.genai import types

    op = cliente.models.generate_videos(
        model=modelo,
        source=types.GenerateVideosSource(
            prompt=prompt,
            image=types.Image(image_bytes=imagen.read_bytes(), mime_type="image/jpeg")),
    )
    for _ in range(90):
        time.sleep(10)
        op = cliente.operations.get(op)
        if op.done:
            break
    respuesta = getattr(op, "response", None)
    if not (respuesta and respuesta.generated_videos):
        motivo = getattr(respuesta, "rai_media_filtered_reasons", None)
        raise RuntimeError(f"Veo no devolvio video (filtro o tiempo agotado): {motivo}")
    cliente.files.download(file=respuesta.generated_videos[0].video)
    respuesta.generated_videos[0].video.save(str(destino))
    return destino


def ultimo_fotograma(video, destino):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i", str(video),
                    "-vframes", "1", "-q:v", "2", str(destino)], check=True)
    return destino


def brillo(imagen):
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-f", "lavfi", f"movie='{imagen}',signalstats",
         "-show_entries", "frame_tags=lavfi.signalstats.YAVG", "-of", "csv=p=0"],
        capture_output=True, text=True)
    try:
        return float(salida.stdout.strip().splitlines()[0])
    except (IndexError, ValueError):
        return None


def comprueba_encadenado(fotograma, acto_siguiente, forzar):
    """Para antes de encadenar desde un fotograma donde ya no se ve el sitio."""
    valor = brillo(fotograma)
    if valor is None or valor >= BRILLO_MINIMO_ENCADENADO:
        return
    aviso = (f"el fotograma para encadenar el acto {acto_siguiente} tiene brillo "
             f"{valor:.0f}, por debajo de {BRILLO_MINIMO_ENCADENADO}: a oscuras el "
             f"modelo no ve la arquitectura y la reinventa.")
    if forzar:
        print(f"  AVISO: {aviso} Se sigue por --forzar.", flush=True)
        return
    sys.exit(f"\nParado: {aviso}\nRehaz el acto anterior dandole una fuente de luz "
             f"que mantenga el sitio visible, o usa --forzar si es a proposito.")


def une(partes, destino):
    entradas = []
    for p in partes:
        entradas += ["-i", str(p)]
    filtro = ("".join(f"[{i}:v][{i}:a]" for i in range(len(partes)))
              + f"concat=n={len(partes)}:v=1:a=1[v][a]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", filtro,
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(destino)],
                   check=True)
    return destino


def main():
    p = argparse.ArgumentParser(description="Genera los actos de un capitulo")
    p.add_argument("ficha", help="JSON del capitulo en prompts/escenas/")
    p.add_argument("--solo-acto", type=int, default=None, metavar="N",
                   help="Rehace solo ese acto. El anterior se conserva con "
                        "sufijo _previo, por si el nuevo sale peor")
    p.add_argument("--ver-prompts", action="store_true",
                   help="Muestra lo que se enviaria y sale, sin gastar cuota")
    p.add_argument("--forzar", action="store_true",
                   help="Encadena aunque el fotograma de partida este muy oscuro")
    p.add_argument("--entrada", default=None, metavar="IMAGEN",
                   help="Con --solo-acto, parte de esta imagen en vez del acto anterior. "
                        "Sirve para probar un acto antes de tener los previos, o para "
                        "empezar desde el final de otro capitulo")
    args = p.parse_args()

    ruta = Path(args.ficha)
    ficha = json.loads(ruta.read_text())
    slug = ruta.stem                                   # cap6_los-que-vuelven
    n_cap = ficha["capitulo"]
    actos = ficha["actos"]

    for campo in ("foto", "arquitectura", "comun"):
        if "PENDIENTE" in str(ficha.get(campo, "")):
            sys.exit(f"La ficha tiene '{campo}' sin completar. Falta rellenarlo antes de gastar cuota.")

    def archivo(acto):
        return ESCENAS / f"cap{n_cap}_{acto['n']}_{acto['nombre'].replace(' ', '-')}.mp4"

    if args.ver_prompts:
        for acto in actos:
            texto = prompt_completo(ficha, acto)
            print(f"--- acto {acto['n']}: {acto['nombre']} ({len(texto)} caracteres) ---")
            print(texto, "\n")
        return 0

    load_env()
    from google import genai
    cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    ESCENAS.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="serie_"))

    if args.solo_acto:
        actual = next((a for a in actos if a["n"] == args.solo_acto), None)
        if actual is None:
            sys.exit(f"La ficha no tiene acto {args.solo_acto}")
        destino = archivo(actual)
        # primero se decide desde donde encadenar, y solo despues se aparta el
        # archivo viejo: si el guardian para, el acto no se queda sin video
        if args.entrada:
            entrada = Path(args.entrada)
            if not entrada.exists():
                sys.exit(f"No existe la imagen de entrada: {entrada}")
            comprueba_encadenado(entrada, actual["n"], args.forzar)
        elif actual["n"] == 1:
            entrada = ROOT / ficha["foto"]
        else:
            anterior = next(a for a in actos if a["n"] == actual["n"] - 1)
            entrada = ultimo_fotograma(archivo(anterior), tmp / "entrada.jpg")
            comprueba_encadenado(entrada, actual["n"], args.forzar)
        if destino.exists():
            previo = destino.with_name(f"{destino.stem}_previo.mp4")
            destino.rename(previo)
            print(f"el anterior se conserva como {previo.name}")
        print(f"[acto {actual['n']}] {actual['nombre']}...", flush=True)
        genera(cliente, ficha["modelo"], prompt_completo(ficha, actual), entrada, destino)
        print(f"  listo: {destino.name}", flush=True)
    else:
        entrada = ROOT / ficha["foto"]
        for i, acto in enumerate(actos):
            print(f"[{acto['n']}/{len(actos)}] {acto['nombre']}...", flush=True)
            salida = genera(cliente, ficha["modelo"], prompt_completo(ficha, acto),
                            entrada, archivo(acto))
            print(f"  listo: {salida.name}", flush=True)
            if i < len(actos) - 1:
                entrada = ultimo_fotograma(salida, tmp / f"fotograma_{acto['n']}.jpg")
                comprueba_encadenado(entrada, actos[i + 1]["n"], args.forzar)
                time.sleep(PAUSA_ENTRE_ACTOS)

    partes = [archivo(a) for a in actos]
    faltan = [p.name for p in partes if not p.exists()]
    if faltan:
        print(f"\nsin unir: faltan {', '.join(faltan)}")
        return 1
    final = une(partes, ESCENAS / f"{slug}_24s.mp4")
    print(f"\nSECUENCIA -> {final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
