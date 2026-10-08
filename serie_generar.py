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
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
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

# xAI: se pide la generacion y se sondea hasta que el video esta listo.
XAI_GENERAR = "https://api.x.ai/v1/videos/generations"
XAI_ESTADO = "https://api.x.ai/v1/videos/{}"

# Tarifa de salida por segundo, para avisar de lo que va a costar. La base de
# la documentacion de xAI es 0,080 $/s; OpenRouter publica hasta 0,25 a 1080p.
# Para 720p no hay dato publico, asi que no se estima.
PRECIO_SEGUNDO = {"480p": 0.08, "1080p": 0.25}


def prompt_completo(ficha, acto):
    """El texto del acto mas lo que se repite en todos: sitio, luz y reglas.

    La arquitectura va copiada en cada acto porque es lo que evita que el
    modelo se invente edificios al encadenar. Las notas de la ficha -nota,
    riesgo, revision...- son para quien la lee y nunca llegan al modelo.
    """
    # un acto puede traer su propia arquitectura o texto comun, cuando cambia
    # de encuadre a mitad de capitulo -del plano aereo a la plaza, por ejemplo-
    partes = [acto["prompt"]]
    # la descripcion del protagonista se copia en todos los actos, igual que la
    # arquitectura: es lo que mantiene al mismo personaje entre capitulos
    # un acto puede quedarse sin protagonista con "personaje": "": en el
    # capitulo 2 el celador mira desde fuera, y describirlo hizo que el modelo
    # lo metiera dentro de la catedral, linterna incluida
    personaje = acto.get("personaje", ficha.get("personaje"))
    if personaje:
        partes.append(personaje)
    partes.append(acto.get("arquitectura", ficha["arquitectura"]))
    luz = acto.get("luz_prompt", ficha.get("luz_prompt"))
    if luz:
        partes.append(luz)
    partes.append(acto.get("comun", ficha["comun"]))
    return " ".join(partes)


def data_uri(ruta):
    # el tipo se lee del contenido y no de la extension: la API de imagen de xAI
    # devuelve JPEG aunque se le pida otra cosa
    tipo = "image/png" if ruta.read_bytes()[:4] == b"\x89PNG" else "image/jpeg"
    return f"data:{tipo};base64," + base64.b64encode(ruta.read_bytes()).decode()


def cuerpo_grok(ficha, prompt, imagen, referencias, acto=None):
    """Peticion para la API de video de xAI.

    Los nombres salen de la documentacion: duration (1-15 s), aspect_ratio,
    resolution, generate_audio, image como fotograma de partida,
    reference_images para anclar el personaje y last_frame para fijar el final.
    """
    cuerpo = {
        "model": ficha["modelo"],
        "prompt": prompt,
        # un acto puede durar menos que los demas: el remate de un capitulo no
        # necesita los mismos segundos que una persecucion
        "duration": (acto or {}).get("duracion_s", ficha.get("duracion_s", 8)),
        "aspect_ratio": ficha.get("formato", "9:16"),
        "resolution": ficha.get("resolucion", "720p"),
        "generate_audio": ficha.get("audio", True),
    }
    if imagen is not None:
        cuerpo["image"] = {"url": data_uri(imagen)}
    if referencias:
        cuerpo["reference_images"] = [{"url": data_uri(r)} for r in referencias]
    return cuerpo


def sin_imagenes(cuerpo):
    """El mismo cuerpo con las imagenes resumidas, para poder leerlo."""
    copia = dict(cuerpo)
    if "image" in copia:
        copia["image"] = f"<imagen de {len(cuerpo['image']['url'])} caracteres>"
    if "reference_images" in copia:
        copia["reference_images"] = f"<{len(cuerpo['reference_images'])} imagenes de referencia>"
    return copia


def _xai(url, datos=None):
    clave = os.environ.get("XAI_API_KEY")
    if not clave:
        sys.exit("Falta XAI_API_KEY en el .env")
    peticion = urllib.request.Request(
        url, data=json.dumps(datos).encode() if datos else None,
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"},
        method="POST" if datos else "GET")
    try:
        with urllib.request.urlopen(peticion, timeout=120) as respuesta:
            return json.loads(respuesta.read())
    except urllib.error.HTTPError as error:
        detalle = error.read().decode(errors="replace")[:500]
        raise RuntimeError(f"xAI respondio {error.code}: {detalle}") from None


def genera_grok(cuerpo, destino, espera=10, sondeos=90):
    inicio = _xai(XAI_GENERAR, cuerpo)
    peticion_id = inicio.get("request_id") or inicio.get("id")
    estado = inicio
    for _ in range(sondeos):
        if estado.get("status") == "done":
            break
        if estado.get("status") in ("failed", "expired"):
            error = estado.get("error", {})
            raise RuntimeError(f"xAI no genero el video: {error.get('code')} {error.get('message')}")
        if not peticion_id:
            raise RuntimeError(f"xAI no devolvio request_id: {json.dumps(inicio)[:300]}")
        time.sleep(espera)
        estado = _xai(XAI_ESTADO.format(peticion_id))
    if estado.get("status") != "done":
        raise RuntimeError("xAI sigue generando despues de esperar demasiado")
    url = estado["video"]["url"]
    with urllib.request.urlopen(url, timeout=300) as fuente:
        destino.write_bytes(fuente.read())
    return destino


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


def medidas(video):
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True)
    ancho, alto = salida.stdout.strip().splitlines()[0].split(",")[:2]
    return int(ancho), int(alto)


def une(partes, destino):
    entradas = []
    for p in partes:
        entradas += ["-i", str(p)]
    # Grok devuelve cada clip con el tamano que le toca segun su imagen de
    # partida -400x736 y 480x848 en el mismo capitulo-, y concat exige que
    # todos midan igual: se llevan al tamano del primero antes de unir.
    # al mayor de los clips, para no perder resolucion
    ancho, alto = max(medidas(p) for p in partes)
    escalado = "".join(
        f"[{i}:v]scale={ancho}:{alto},setsar=1[v{i}];" for i in range(len(partes)))
    filtro = (escalado
              + "".join(f"[v{i}][{i}:a]" for i in range(len(partes)))
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
    p.add_argument("--ver-peticion", action="store_true",
                   help="Con Grok, muestra el cuerpo de la peticion y sale, sin gastar nada")
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
    # cada serie puede guardar sus clips en su propia carpeta
    escenas = ROOT / ficha["salida"] if ficha.get("salida") else ESCENAS

    for campo in ("foto", "arquitectura", "comun"):
        if "PENDIENTE" in str(ficha.get(campo, "")):
            sys.exit(f"La ficha tiene '{campo}' sin completar. Falta rellenarlo antes de gastar cuota.")

    def imagen_propia(relativa):
        # un acto con "entrada" arranca de esa imagen en vez de encadenar: un
        # salto de lugar o de tiempo dentro del capitulo
        ruta_imagen = ROOT / relativa
        if not ruta_imagen.exists():
            sys.exit(f"No existe la imagen de partida: {ruta_imagen}")
        return ruta_imagen

    def archivo(acto):
        # cada serie con su prefijo: los capitulos de dos series no se pisan
        prefijo = ficha.get("prefijo", "cap")
        return escenas / f"{prefijo}{n_cap}_{acto['n']}_{acto['nombre'].replace(' ', '-')}.mp4"

    if args.ver_prompts:
        for acto in actos:
            texto = prompt_completo(ficha, acto)
            print(f"--- acto {acto['n']}: {acto['nombre']} ({len(texto)} caracteres) ---")
            print(texto, "\n")
        return 0

    load_env()
    es_grok = str(ficha["modelo"]).startswith("grok")
    def imagenes_de(patrones):
        encontradas_todas = []
        for patron in patrones:
            encontradas = sorted(ROOT.glob(patron)) if any(c in patron for c in "*?[") else [ROOT / patron]
            if not encontradas:
                sys.exit(f"Ninguna imagen de referencia coincide con {patron}: sin ellas el "
                         f"personaje sale distinto en cada acto.")
            for imagen in encontradas:
                if not imagen.exists():
                    sys.exit(f"Falta la imagen de referencia: {imagen}")
                encontradas_todas.append(imagen)
        return encontradas_todas

    referencias = imagenes_de(ficha.get("referencias", []))

    cliente = None
    if not es_grok:
        from google import genai
        cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    escenas.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="serie_"))

    def genera_acto(prompt, entrada, destino, acto=None):
        if not es_grok:
            return genera(cliente, ficha["modelo"], prompt, entrada, destino)
        # un acto sin protagonista tampoco lleva sus fotos: adjuntarlas invita
        # al modelo a colocarlo en la escena
        propias = acto.get("referencias") if acto else None
        del_acto = imagenes_de(propias) if propias is not None else referencias
        cuerpo = cuerpo_grok(ficha, prompt, entrada, del_acto, acto)
        if args.ver_peticion:
            print(json.dumps(sin_imagenes(cuerpo), ensure_ascii=False, indent=2))
            sys.exit(0)
        segundos = cuerpo["duration"]
        precio = PRECIO_SEGUNDO.get(cuerpo["resolution"])
        coste = f", unos {segundos * precio:.2f} $" if precio else ""
        print(f"  {segundos}s a {cuerpo['resolution']} en {cuerpo['aspect_ratio']}"
              f"{', con ' + str(len(del_acto)) + ' referencias' if del_acto else ''}{coste}",
              flush=True)
        return genera_grok(cuerpo, destino)

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
        elif actual.get("entrada"):
            entrada = imagen_propia(actual["entrada"])
        elif actual["n"] == 1:
            entrada = imagen_propia(ficha["foto"])
        else:
            anterior = next(a for a in actos if a["n"] == actual["n"] - 1)
            entrada = ultimo_fotograma(archivo(anterior), tmp / "entrada.jpg")
            comprueba_encadenado(entrada, actual["n"], args.forzar)
        if destino.exists() and not args.ver_peticion:
            previo = destino.with_name(f"{destino.stem}_previo.mp4")
            contador = 1
            while previo.exists():
                # no se pisa un previo anterior: cada intento descartado se guarda
                contador += 1
                previo = destino.with_name(f"{destino.stem}_previo{contador}.mp4")
            destino.rename(previo)
            print(f"el anterior se conserva como {previo.name}")
        print(f"[acto {actual['n']}] {actual['nombre']}...", flush=True)
        genera_acto(prompt_completo(ficha, actual), entrada, destino, actual)
        print(f"  listo: {destino.name}", flush=True)
    else:
        entrada = imagen_propia(ficha["foto"])
        for i, acto in enumerate(actos):
            if acto.get("entrada"):
                entrada = imagen_propia(acto["entrada"])
            print(f"[{acto['n']}/{len(actos)}] {acto['nombre']}...", flush=True)
            salida = genera_acto(prompt_completo(ficha, acto), entrada, archivo(acto), acto)
            print(f"  listo: {salida.name}", flush=True)
            if i < len(actos) - 1:
                if not actos[i + 1].get("entrada"):
                    entrada = ultimo_fotograma(salida, tmp / f"fotograma_{acto['n']}.jpg")
                    comprueba_encadenado(entrada, actos[i + 1]["n"], args.forzar)
                time.sleep(PAUSA_ENTRE_ACTOS)

    partes = [archivo(a) for a in actos]
    faltan = [p.name for p in partes if not p.exists()]
    if faltan:
        print(f"\nsin unir: faltan {', '.join(faltan)}")
        return 1
    final = une(partes, escenas / f"{slug}_24s.mp4")
    print(f"\nSECUENCIA -> {final}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
