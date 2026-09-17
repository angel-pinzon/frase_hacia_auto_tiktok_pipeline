"""Genera las imagenes fijas de la serie con la API de imagen de xAI.

Hace dos cosas, segun la ficha que recibe:

- Una ficha de personaje: la hoja de personaje, los retratos de referencia que
  despues se adjuntan a cada video para que el protagonista sea el mismo.
- Una ficha de capitulo: sus "imagenes_previas", las fotos editadas -de noche,
  sin gente, sin estatua...- de las que arrancan los actos.

    python serie_imagenes.py prompts/personajes/celador.json --solo 1
    python serie_imagenes.py prompts/personajes/celador.json --desde 2
    python serie_imagenes.py prompts/escenas/cel1_el-pedestal-vacio.json
    python serie_imagenes.py prompts/escenas/cel1_el-pedestal-vacio.json --ver-peticion

El primer retrato sale solo del texto. Los demas se piden como edicion del
primero, para que la cara sea la misma: por eso conviene generar el 1, mirarlo,
y solo si convence seguir con --desde 2.

Gasta saldo: entre 0,04 y 0,08 $ por imagen con grok-imagine-image-2.0.
"""

import argparse
import base64
import json
import sys
import urllib.request
from pathlib import Path

from pipeline_utils import load_env
from serie_generar import ROOT, _xai, data_uri

XAI_IMAGEN = "https://api.x.ai/v1/images/generations"
XAI_EDICION = "https://api.x.ai/v1/images/edits"

# Precio por imagen segun /v1/image-generation-models, consultado el 16-09-2026
PRECIO_IMAGEN = {("low", "1k"): 0.04, ("low", "2k"): 0.06,
                 ("medium", "1k"): 0.06, ("medium", "2k"): 0.08}


def cuerpo_imagen(hoja, prompt, referencia):
    cuerpo = {"model": hoja.get("modelo", "grok-imagine-image-2.0"),
              "prompt": prompt,
              "n": 1,
              "response_format": "b64_json"}
    for campo in ("aspect_ratio", "resolution", "quality"):
        if hoja.get(campo):
            cuerpo[campo] = hoja[campo]
    if referencia is not None:
        cuerpo["image"] = {"url": data_uri(referencia), "type": "image_url"}
    return cuerpo


def guarda_imagen(respuesta, destino):
    dato = respuesta["data"][0]
    if dato.get("b64_json"):
        destino.write_bytes(base64.b64decode(dato["b64_json"]))
    else:
        with urllib.request.urlopen(dato["url"], timeout=120) as fuente:
            destino.write_bytes(fuente.read())
    return destino


def aparta(destino, carpeta):
    """Mueve una imagen existente a _previos/ sin pisar las anteriores.

    Fuera de la carpeta de referencias, para que el comodin de las fichas de
    video no adjunte tambien las versiones descartadas.
    """
    previos = carpeta / "_previos"
    previos.mkdir(exist_ok=True)
    apartado = previos / destino.name
    contador = 1
    while apartado.exists():
        contador += 1
        apartado = previos / f"{destino.stem}_{contador}{destino.suffix}"
    destino.rename(apartado)
    print(f"  el anterior se conserva en _previos/{apartado.name}")


def previas(ficha, args):
    """Las imagenes de partida editadas que declara una ficha de capitulo."""
    lista = ficha.get("imagenes_previas", [])
    if not lista:
        sys.exit("La ficha no tiene hoja_de_personaje ni imagenes_previas.")
    ajustes = {"modelo": ficha.get("modelo_imagen", "grok-imagine-image-2.0"),
               "aspect_ratio": ficha.get("formato", "9:16"),
               "resolution": "1k", "quality": "medium"}
    precio = PRECIO_IMAGEN[("medium", "1k")]
    numeros = [args.solo] if args.solo else range(1, len(lista) + 1)
    load_env()
    for n in numeros:
        previa = lista[n - 1]
        origen, destino = ROOT / previa["origen"], ROOT / previa["destino"]
        if not origen.exists():
            sys.exit(f"No existe la foto de origen: {origen}")
        cuerpo = cuerpo_imagen(ajustes, previa["instruccion"], origen)
        if args.ver_peticion:
            vista = dict(cuerpo, image=f"<{origen.name}>")
            print(f"--- {n}: {origen.name} -> {destino.name}")
            print(json.dumps(vista, ensure_ascii=False, indent=2))
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            aparta(destino, destino.parent)
        print(f"[{n}/{len(lista)}] {origen.name} -> {destino.name}, unos {precio:.2f} $", flush=True)
        guarda_imagen(_xai(XAI_EDICION, cuerpo), destino)
        print(f"  listo: {destino.relative_to(ROOT)}", flush=True)
    return 0


def main():
    p = argparse.ArgumentParser(description="Genera la hoja de personaje")
    p.add_argument("ficha", help="JSON del personaje en prompts/personajes/")
    p.add_argument("--solo", type=int, metavar="N", help="Genera solo el retrato N (desde 1)")
    p.add_argument("--desde", type=int, metavar="N", help="Genera del retrato N al final")
    p.add_argument("--ver-peticion", action="store_true",
                   help="Muestra lo que se enviaria, sin gastar nada")
    args = p.parse_args()

    ficha = json.loads(Path(args.ficha).read_text())
    if "hoja_de_personaje" not in ficha:
        return previas(ficha, args)
    hoja = ficha["hoja_de_personaje"]
    carpeta = ROOT / hoja["carpeta"]
    prompts = [t.replace("{descripcion}", ficha["descripcion"]) for t in hoja["imagenes"]]
    numeros = list(range(1, len(prompts) + 1))
    if args.solo:
        numeros = [args.solo]
    elif args.desde:
        numeros = numeros[args.desde - 1:]

    def archivo(n):
        return carpeta / f"{ficha['personaje'].replace(' ', '_')}_{n}.jpg"

    load_env()
    carpeta.mkdir(parents=True, exist_ok=True)
    precio = PRECIO_IMAGEN.get((hoja.get("quality", "medium"), hoja.get("resolution", "1k")))
    for n in numeros:
        # el 1 nace del texto; los demas son el mismo hombre, editado desde el 1
        referencia = None
        if n > 1:
            referencia = archivo(1)
            if not referencia.exists() and not args.ver_peticion:
                sys.exit(f"Falta el retrato 1 ({referencia.name}): los demas parten de el.")
        cuerpo = cuerpo_imagen(hoja, prompts[n - 1], referencia if referencia and referencia.exists() else None)
        if args.ver_peticion:
            vista = dict(cuerpo)
            if "image" in vista:
                vista["image"] = f"<{referencia.name}>"
            print(f"--- retrato {n} -> {'edicion' if referencia else 'generacion'}")
            print(json.dumps(vista, ensure_ascii=False, indent=2))
            continue
        destino = archivo(n)
        if destino.exists():
            aparta(destino, carpeta)
        coste = f", unos {precio:.2f} $" if precio else ""
        print(f"[{n}/{len(prompts)}] {'edicion del retrato 1' if referencia else 'desde texto'}{coste}",
              flush=True)
        respuesta = _xai(XAI_EDICION if referencia else XAI_IMAGEN, cuerpo)
        guarda_imagen(respuesta, destino)
        print(f"  listo: {destino.relative_to(ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
