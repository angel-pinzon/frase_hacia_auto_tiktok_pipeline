"""Genera una imagen realista con Grok Imagine desde una descripcion.

Para probar ideas sueltas, sin fichas ni series.

    python imagen.py "un celador de noche frente a la catedral, con niebla"
    python imagen.py "la balsa muisca flotando en el aire" --formato 16:9
    python imagen.py "la misma plaza pero de noche" --desde foto.jpg
    python imagen.py "un gato" --veces 3 --salida pruebas/gato.jpg
    python imagen.py "un gato" --ver-peticion        # sin gastar nada

Con --desde parte de una imagen y la edita; sin ella, la crea desde el texto.
Gasta saldo de xAI: 0,06 $ por imagen a 1k, 0,08 $ a 2k.
"""

import argparse
import re
import sys
import time
from pathlib import Path

from pipeline_utils import load_env
from serie_generar import ROOT, _xai
from serie_imagenes import PRECIO_IMAGEN, XAI_EDICION, XAI_IMAGEN, cuerpo_imagen, guarda_imagen

CARPETA = ROOT / "output" / "imagenes"

# Sin esto, el modelo se va a ilustracion o a render 3D en cuanto la
# descripcion suena a fantasia. Se puede quitar con --tal-cual.
REALISTA = ("Fotografia realista, como tomada con camara, con luz natural creible, "
            "profundidad de campo y grano fino. Nada de ilustracion, dibujo animado, "
            "render 3D ni aspecto de videojuego. Sin textos ni logotipos.")


def nombre(descripcion):
    limpio = re.sub(r"[^a-z0-9]+", "-", descripcion.lower())[:40].strip("-")
    return f"{limpio}-{time.strftime('%H%M%S')}.jpg"


def main():
    p = argparse.ArgumentParser(description="Genera una imagen con Grok Imagine")
    p.add_argument("descripcion", help="Lo que se quiere ver, en una frase")
    p.add_argument("--desde", metavar="IMAGEN", default=None,
                   help="Parte de esta imagen y la edita, en vez de crearla desde cero")
    p.add_argument("--formato", default="9:16", metavar="W:H",
                   help="Proporcion: 9:16 (por defecto), 16:9, 1:1, 3:4...")
    p.add_argument("--calidad", default="medium", choices=("low", "medium"))
    p.add_argument("--resolucion", default="1k", choices=("1k", "2k"))
    p.add_argument("--veces", type=int, default=1, metavar="N",
                   help="Genera N variantes de la misma descripcion")
    p.add_argument("--salida", default=None, metavar="RUTA",
                   help=f"Archivo de salida; por defecto, dentro de {CARPETA.relative_to(ROOT)}/")
    p.add_argument("--tal-cual", action="store_true",
                   help="No anade la coletilla que fuerza el aspecto fotografico")
    p.add_argument("--ver-peticion", action="store_true",
                   help="Muestra lo que se enviaria y sale, sin gastar nada")
    args = p.parse_args()

    texto = args.descripcion
    if not args.tal_cual:
        texto = f"{texto.rstrip('. ')}. {REALISTA}"

    origen = None
    if args.desde:
        origen = Path(args.desde)
        if not origen.exists():
            origen = ROOT / args.desde
        if not origen.exists():
            sys.exit(f"No existe la imagen de partida: {args.desde}")

    ajustes = {"aspect_ratio": args.formato, "resolution": args.resolucion,
               "quality": args.calidad}
    cuerpo = cuerpo_imagen(ajustes, texto, origen)
    if args.ver_peticion:
        import json
        vista = dict(cuerpo)
        if "image" in vista:
            vista["image"] = f"<{origen.name}>"
        print(json.dumps(vista, ensure_ascii=False, indent=2))
        return 0

    precio = PRECIO_IMAGEN[(args.calidad, args.resolucion)]
    load_env()
    for i in range(args.veces):
        if args.salida:
            destino = Path(args.salida)
            if args.veces > 1 and i:
                destino = destino.with_name(f"{destino.stem}_{i + 1}{destino.suffix}")
        else:
            destino = CARPETA / nombre(args.descripcion)
        destino.parent.mkdir(parents=True, exist_ok=True)
        print(f"[{i + 1}/{args.veces}] {'editando ' + origen.name if origen else 'desde texto'}, "
              f"{args.resolucion} {args.formato}, unos {precio:.2f} $", flush=True)
        guarda_imagen(_xai(XAI_EDICION if origen else XAI_IMAGEN, cuerpo), destino)
        print(f"  {destino}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
