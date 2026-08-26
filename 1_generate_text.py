"""Fase 1: extrae una frase motivadora de las letras locales del personaje activo."""

import json
import os
import random
import re
import sys
import time
import unicodedata

from pipeline_utils import active_character, load_config, load_env, output_dir, resolve

NO_MATCH = "SIN_FRAGMENTO"


def load_songs(character):
    lyrics_dir = resolve(character["lyrics_dir"])
    if not lyrics_dir.is_dir():
        raise FileNotFoundError(f"No existe la carpeta de letras: {lyrics_dir}")

    # Con 'top_songs' solo se citan los exitos, que es lo que la gente reconoce.
    top = character.get("top_songs")
    if top:
        songs = [lyrics_dir / f"{slug}.txt" for slug in top]
        faltan = [path.name for path in songs if not path.exists()]
        if faltan:
            raise FileNotFoundError(f"Faltan letras de 'top_songs': {', '.join(faltan)}")
    else:
        songs = sorted(lyrics_dir.glob("*.txt"))

    songs = [path for path in songs if path.stat().st_size]
    if not songs:
        raise FileNotFoundError(f"No hay archivos .txt con letras en {lyrics_dir}")
    return songs


def to_speech(verses):
    """Cada salto de verso pasa a ser una coma: el TTS entona por puntuacion."""
    lines = [line.strip() for line in verses.splitlines() if line.strip()]
    spoken = []
    for i, line in enumerate(lines):
        if i < len(lines) - 1 and line[-1] not in ".,;:!?":
            line += ","
        spoken.append(line)
    return " ".join(spoken)


def song_title(path):
    """El nombre del archivo es el titulo en slug: a-mi-papa -> A Mi Papa."""
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def clean_lyrics(text):
    """El scraper perdio los saltos de estrofa y dejo palabras pegadas."""
    text = re.sub(r"([a-záéíóúñ,])([A-ZÁÉÍÓÚÑ¡])", r"\1\n\n\2", text)
    text = re.sub(r"\(\s*bis\s*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize(text):
    """Compara ignorando tildes, mayusculas, puntuacion y saltos de linea."""
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9ñ ]+", " ", text).strip()


def is_verbatim(fragment, lyrics):
    return " ".join(normalize(fragment).split()) in " ".join(normalize(lyrics).split())


def ask_gemini(client, config, prompt):
    from google.genai import errors, types

    request_config = None
    if config["gemini"].get("use_search"):
        request_config = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())]
        )

    # 503 y 429 son picos de demanda: se reintenta en vez de tumbar el pipeline.
    espera = config["gemini"].get("retry_wait", 20)
    for intento in range(1, config["gemini"].get("api_retries", 4) + 1):
        try:
            response = client.models.generate_content(
                model=config["gemini"]["model"],
                contents=prompt,
                config=request_config,
            )
            return (response.text or "").strip().strip('"')
        except (errors.ServerError, errors.ClientError) as error:
            if error.code not in (429, 500, 502, 503) or intento == 4:
                raise
            print(f"  API saturada ({error.code}), reintento {intento} en {espera}s")
            time.sleep(espera)
            espera *= 2


def generate_text(config):
    from google import genai

    load_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Falta GEMINI_API_KEY. Definela en el entorno o en un archivo .env"
        )

    character = active_character(config)
    songs = load_songs(character)
    client = genai.Client(api_key=api_key)

    min_words = config["gemini"].get("min_words", 14)
    attempts = min(config["gemini"].get("max_attempts", 3), len(songs))
    for song_path in random.sample(songs, attempts):
        song = song_title(song_path)
        lyrics = clean_lyrics(song_path.read_text(encoding="utf-8"))
        print(f"Cancion consultada: {song}")

        prompt = character["prompt"].replace("{song}", song).replace("{lyrics}", lyrics)
        fragment = ask_gemini(client, config, prompt)

        if not fragment or NO_MATCH in fragment.upper():
            print("  -> el modelo no encontro un fragmento util, probando otra")
            continue
        if not is_verbatim(fragment, lyrics):
            print("  -> descartado: el fragmento no aparece literal en la letra")
            continue
        # Menos palabras dan clips de 3-4s, que en TikTok rinden mal.
        palabras = len(fragment.split())
        if palabras < min_words:
            print(f"  -> descartado: solo {palabras} palabras (minimo {min_words})")
            continue

        return fragment, {"song": song, "source": str(song_path), "verbatim": True}

    raise RuntimeError(
        f"No se obtuvo un fragmento textual tras {attempts} intentos. "
        "Revisa las letras o sube 'gemini.max_attempts' en config.json"
    )


def generate_free_text(config):
    """Modo libre: escribe frases al estilo del personaje, sin citar una cancion.

    No hay verificacion literal porque no es una cita. Para no atribuir algo
    inventado a una obra concreta, 'song' se deja vacio y no sale rotulo.
    """
    from google import genai

    load_env()
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GEMINI_API_KEY. Definela en el entorno o en un .env")

    character = active_character(config)
    if not character.get("prompt_libre"):
        raise KeyError(
            f"El personaje activo no tiene 'prompt_libre' en config.json"
        )

    settings = config["gemini"]
    songs = load_songs(character)
    muestras = random.sample(songs, min(settings.get("context_songs", 6), len(songs)))
    contexto = "\n\n---\n\n".join(
        f'CANCIÓN "{song_title(p)}":\n{clean_lyrics(p.read_text(encoding="utf-8"))}'
        for p in muestras
    )
    print("Letras usadas como contexto:")
    for p in muestras:
        print(f"  - {song_title(p)}")

    minimo = settings.get("free_min_words", 40)
    maximo = settings.get("free_max_words", 70)
    prompt = (character["prompt_libre"]
              .replace("{lyrics}", contexto)
              .replace("{min}", str(minimo))
              .replace("{max}", str(maximo)))

    # El modelo puede copiar versos aunque se le prohiba: aqui se comprueba
    # lo contrario que en el modo cita, que NADA sea textual.
    corpus = " ".join(clean_lyrics(p.read_text(encoding="utf-8")) for p in songs)

    client = genai.Client(api_key=api_key)
    for intento in range(1, settings.get("max_attempts", 5) + 1):
        texto = ask_gemini(client, config, prompt)
        palabras = len(texto.split()) if texto else 0

        copiadas = [l for l in texto.splitlines()
                    if len(l.split()) >= 5 and is_verbatim(l, corpus)]
        if copiadas:
            print(f"  intento {intento}: copio {len(copiadas)} linea(s) de las letras")
            continue

        if minimo <= palabras <= maximo:
            return texto, {
                "song": "",
                "source": "generado en modo libre",
                "verbatim": False,
                "mode": "libre",
                "context_songs": [song_title(p) for p in muestras],
            }
        print(f"  intento {intento}: {palabras} palabras, fuera de {minimo}-{maximo}")

    raise RuntimeError(f"No se logro un texto de {minimo}-{maximo} palabras")


def main():
    config = load_config()
    libre = "--libre" in sys.argv
    phrase, meta = generate_free_text(config) if libre else generate_text(config)
    out = output_dir(config)

    # El TTS lee una sola linea; los versos se conservan para los subtitulos.
    meta["verses"] = phrase
    (out / "script.txt").write_text(to_speech(phrase), encoding="utf-8")
    (out / "script_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n[1/4] Guion generado -> {out / 'script.txt'}")
    print(f"\n  {phrase}\n")
    if meta.get("mode") == "libre":
        print(f"  Texto original ({len(phrase.split())} palabras), sin atribuir a ninguna cancion")
    else:
        print(f"  Fuente verificada: {meta['song']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
