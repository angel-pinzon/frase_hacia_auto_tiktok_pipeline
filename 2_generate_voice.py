"""Fase 2: sintetiza el guion con la voz clonada del personaje activo (OmniVoice).

OmniVoice falla de forma aleatoria, asi que cada toma se diagnostica y se
regenera hasta que sale limpia. Se buscan cuatro defectos:

- final cortado: la ultima silaba termina en seco;
- palabra atropellada: alguna se comprime hasta no entenderse;
- frase corrida: falta la pausa donde el texto pone "..." o punto;
- texto incompleto: se salta o deforma palabras.

Entre intentos se adapta: si atropella, baja la velocidad; si una pausa no
aparece, cambia ese punto por puntos suspensivos, que OmniVoice respeta mas.
Si se agotan los intentos, se queda con la mejor toma y no con la ultima.
"""

import json
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata
import wave
from difflib import SequenceMatcher
from pathlib import Path

from pipeline_utils import active_character, load_config, output_dir, resolve

FRAME = 0.025     # ventana de analisis en segundos
SILENCIO = 50     # RMS por debajo del cual se considera silencio

# Peso de cada defecto al elegir la mejor toma cuando ninguna sale limpia.
GRAVEDAD = {"corte": 10, "texto": 10, "atropello": 4, "pausa": 2}


def tail_level(path):
    """Energia con la que termina el audio: alta = OmniVoice corto en seco."""
    with wave.open(str(path), "rb") as wav:
        frames, rate = wav.getnframes(), wav.getframerate()
        samples = struct.unpack(f"<{frames}h", wav.readframes(frames))

    window = int(rate * FRAME)
    envelope = []
    for i in range(0, frames, window):
        chunk = samples[i:i + window]
        if chunk:
            envelope.append((sum(x * x for x in chunk) / len(chunk)) ** 0.5)

    return next((v for v in reversed(envelope) if v > SILENCIO), 0.0)


ANALISIS = r"""
import json, re, subprocess, sys, warnings, logging
warnings.filterwarnings('ignore'); logging.getLogger('transformers').setLevel(logging.ERROR)
import soundfile as sf
from transformers import pipeline

ruta, min_pausa, ruido = sys.argv[1], float(sys.argv[2]), sys.argv[3]
asr = pipeline('automatic-speech-recognition', model='openai/whisper-large-v3-turbo', device=0)
kw = {'language': 'spanish'}

completo = asr(ruta, generate_kwargs=kw, return_timestamps='word')
palabras = [[c['text'], c['timestamp'][0], c['timestamp'][1]] for c in completo['chunks']]

# Las marcas de tiempo por palabra no sirven para medir pausas: Whisper estira
# las palabras sobre el silencio. Se corta el audio por los silencios reales y
# se transcribe cada trozo, para saber con que palabra termina cada frase.
audio, sr = sf.read(ruta, dtype='float32')
if audio.ndim > 1:
    audio = audio.mean(axis=1)
total = len(audio) / sr
err = subprocess.run(['ffmpeg', '-v', 'info', '-i', ruta, '-af',
                      f'silencedetect=noise={ruido}dB:d={min_pausa}', '-f', 'null', '-'],
                     capture_output=True, text=True).stderr
ini = [float(x) for x in re.findall(r'silence_start: ([0-9.]+)', err)]
fin = [float(x) for x in re.findall(r'silence_end: ([0-9.]+)', err)]
cortes = [((a + b) / 2, b - a) for a, b in zip(ini, fin) if a > 0.05 and b < total - 0.05]

trozos = []
limites = [(0.0, 0.0)] + cortes
for i, (t0, _) in enumerate(limites):
    t1 = limites[i + 1][0] if i + 1 < len(limites) else total
    pausa = limites[i + 1][1] if i + 1 < len(limites) else 0.0
    # un trozo de medio segundo suele ser ruido, y ahi Whisper se inventa palabras
    if trozos and t1 - t0 < 0.5:
        trozos[-1][1], trozos[-1][3] = t1, pausa
        continue
    trozos.append([t0, t1, '', pausa])
for trozo in trozos:
    segmento = audio[int(trozo[0] * sr):int(trozo[1] * sr)]
    trozo[2] = asr({'raw': segmento, 'sampling_rate': sr}, generate_kwargs=kw)['text'].strip()

print(json.dumps({'texto': completo['text'], 'palabras': palabras, 'trozos': trozos}))
"""


def analiza(config, path):
    """Transcripcion completa, palabras con tiempos y frases entre silencios."""
    settings = config["omnivoice"]
    result = subprocess.run(
        [settings["python"], "-c", ANALISIS, str(path),
         str(settings.get("pausa_minima_detectable", 0.12)), str(settings.get("ruido_db", -32))],
        capture_output=True, text=True, cwd=settings.get("cwd") or None,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout.strip().splitlines()[-1])
    except json.JSONDecodeError:
        return None


def normaliza(palabra):
    palabra = unicodedata.normalize("NFD", palabra.lower())
    palabra = "".join(c for c in palabra if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9ñ]", "", palabra)


def palabras_de(texto):
    return [n for n in (normaliza(x) for x in re.findall(r"\w+", texto)) if n]


def pausas_esperadas(texto):
    """Sitios donde el texto pide pausa: puntos suspensivos y puntos.

    Las comas no cuentan: OmniVoice apenas se detiene en ellas (0,08 s
    medidos), asi que exigirlas haria fallar tomas buenas. El punto final del
    texto tampoco, porque despues no hay nada.
    """
    esperadas = []
    marcas = list(re.finditer(r"\w+|\.\.\.|\.", texto))
    for i, m in enumerate(marcas):
        if m.group() not in ("...", ".") or i == 0 or not re.match(r"\w", marcas[i - 1].group()):
            continue
        if not any(re.match(r"\w", x.group()) for x in marcas[i + 1:]):
            continue
        esperadas.append({"palabra": marcas[i - 1].group(), "tipo": m.group(), "pos": m.start()})
    return esperadas


def pausas_que_faltan(esperadas, trozos, minimos):
    """Compara las pausas pedidas con los finales de frase reales, en orden.

    `minimos` da la pausa exigida a cada una, por orden de aparicion.
    """
    finales = []
    for _, _, texto, pausa in trozos[:-1]:
        palabras = palabras_de(texto)
        if palabras:
            finales.append((palabras[-1], pausa))

    faltan, desde = [], 0
    for k, esperada in enumerate(esperadas):
        objetivo = normaliza(esperada["palabra"])
        encontrada = None
        for j in range(desde, len(finales)):
            if SequenceMatcher(None, finales[j][0], objetivo).ratio() >= 0.8:
                encontrada = j
                break
        medida = round(finales[encontrada][1], 2) if encontrada is not None else 0.0
        if encontrada is not None:
            desde = encontrada + 1
        # se compara lo que se muestra: si no, 0,198 aparece como "0.20" y falla
        if medida < minimos[k]:
            faltan.append({**esperada, "orden": k, "medida": medida})
    return faltan


def palabra_mas_corta(palabras):
    """Palabra mas comprimida: OmniVoice a veces se come silabas."""
    peor = None
    for texto, inicio, fin in palabras:
        palabra = texto.strip(" ,.;:!?")
        if fin is None or len(palabra) <= 3:
            continue
        if peor is None or fin - inicio < peor[1]:
            peor = (palabra, fin - inicio)
    return peor


def diagnostica(config, path, texto, original=None):
    """Defectos de una toma, cada uno con su gravedad.

    `texto` es lo que se sintetizo; `original`, lo que se pidio antes de
    adaptarlo. Las pausas se exigen segun el original: cambiar un punto por
    '...' es para asegurar esa pausa, no para pedirle mas.
    """
    settings = config["omnivoice"]
    defectos = []

    nivel = tail_level(path)
    if nivel > settings.get("cut_threshold", 250):
        defectos.append({"tipo": "corte", "detalle": f"final cortado (nivel {nivel:.0f})"})
        return defectos, {"final": round(nivel)}     # no merece la pena transcribir

    analisis = analiza(config, path)
    if analisis is None:
        return defectos, {"final": round(nivel), "analisis": "fallo al transcribir"}

    peor = palabra_mas_corta(analisis["palabras"])
    if peor and peor[1] < settings.get("min_word_duration", 0.13):
        defectos.append({"tipo": "atropello", "detalle": f"'{peor[0]}' atropellada ({peor[1]:.2f}s)"})

    cobertura = SequenceMatcher(None, palabras_de(texto), palabras_de(analisis["texto"])).ratio()
    if cobertura < settings.get("min_cobertura", 0.85):
        defectos.append({"tipo": "texto", "detalle": f"texto incompleto o deformado (cobertura {cobertura:.2f})"})

    exigencia = {"...": settings.get("pausa_suspensivos", 0.2), ".": settings.get("pausa_punto", 0.12)}
    esperadas = pausas_esperadas(texto)
    pedidas = pausas_esperadas(original or texto)
    minimos = [exigencia[(pedidas[k] if k < len(pedidas) else e)["tipo"]] for k, e in enumerate(esperadas)]
    for falta in pausas_que_faltan(esperadas, analisis["trozos"], minimos):
        defectos.append({"tipo": "pausa", "orden": falta["orden"], "marca": falta["tipo"],
                         "detalle": f"sin pausa tras '{falta['palabra']}{falta['tipo']}' ({falta['medida']:.2f}s)"})

    detalle = {"final": round(nivel), "cobertura": round(cobertura, 2),
               "transcripcion": analisis["texto"].strip(),
               "frases": [f"{t} ({p:.2f}s)" for _, _, t, p in analisis["trozos"]]}
    if peor:
        detalle["palabra_mas_corta"] = [peor[0], round(peor[1], 2)]
    return defectos, detalle


def con_suspensivos(texto, ordenes):
    """Cambia por '...' los puntos de las pausas indicadas."""
    posiciones = [e["pos"] for k, e in enumerate(pausas_esperadas(texto)) if k in ordenes and e["tipo"] == "."]
    for pos in sorted(posiciones, reverse=True):
        texto = texto[:pos] + "..." + texto[pos + 1:]
    return texto


def texto_a_sintetizar(config, character, script_text):
    # OmniVoice recorta el final de la ultima palabra: la coletilla absorbe el corte.
    # Cada personaje tiene la suya; si no, se usa la global.
    suffix = character.get("text_suffix", config["omnivoice"].get("text_suffix", ""))
    # El guion suele acabar en punto y la coletilla empieza por ". ": sin esto
    # quedaba "bendicion.. Con mucho Gusto", y al reforzar la pausa, cuatro puntos.
    if suffix.startswith(".") and re.search(r"[.!?]$", script_text):
        suffix = " " + suffix.lstrip(". ")
    return script_text + suffix


def build_command(config, character, gen_text, destination, speed=None):
    settings = config["omnivoice"]
    ref_audio = resolve(character["audio_path"])
    if not ref_audio.exists():
        raise FileNotFoundError(f"No se encuentra el audio de referencia: {ref_audio}")

    placeholders = {
        "ref_audio": str(ref_audio),
        "ref_text": character["audio_text"],
        "gen_text": gen_text,
        "output": str(destination),
    }
    args = [arg.format(**placeholders) for arg in settings["args"]]
    speed = speed if speed is not None else settings.get("speed")
    if speed:
        args += ["--speed", f"{speed:.2f}"]
    return [settings["python"], "-m", settings["module"], *args]


def main():
    config = load_config()
    out = output_dir(config)
    character = active_character(config)

    script_path = out / "script.txt"
    if not script_path.exists():
        raise FileNotFoundError(f"Ejecuta primero la fase 1: falta {script_path}")
    script_text = script_path.read_text(encoding="utf-8").strip()

    settings = config["omnivoice"]
    destination = out / "voice.wav"
    intentos = settings.get("max_attempts", 3)
    adaptar = settings.get("adaptar", True)

    original = texto_a_sintetizar(config, character, script_text)
    texto = original
    velocidad = settings.get("speed")
    suspensivos = set()          # pausas cuyo punto ya se cambio por '...'
    registro = []
    tmp = Path(tempfile.mkdtemp(prefix="voz_"))

    for intento in range(1, intentos + 1):
        toma = tmp / f"intento_{intento}.wav"
        subprocess.run(build_command(config, character, texto, toma, velocidad),
                       check=True, cwd=settings.get("cwd") or None)
        if not toma.exists():
            raise RuntimeError(f"OmniVoice no genero el audio esperado en {toma}")

        defectos, detalle = diagnostica(config, toma, texto, original)
        gravedad = sum(GRAVEDAD[d["tipo"]] for d in defectos)
        registro.append({"intento": intento, "texto": texto, "velocidad": velocidad,
                         "defectos": [d["detalle"] for d in defectos], "gravedad": gravedad,
                         "archivo": str(toma), **detalle})

        if not defectos and detalle.get("analisis"):
            print(f"Intento {intento}: final limpio, pero {detalle['analisis']}: "
                  "no se comprobaron pausas, texto ni palabras atropelladas")
            break
        if not defectos:
            corta = detalle.get("palabra_mas_corta")
            extra = f", palabra mas corta '{corta[0]}' {corta[1]:.2f}s" if corta else ""
            print(f"Intento {intento}: limpio (final {detalle['final']}{extra})")
            break

        print(f"Intento {intento}: " + "; ".join(d["detalle"] for d in defectos))
        if intento == intentos or not adaptar:
            continue

        # Decidir como cambiar la siguiente toma
        cambios = []
        if any(d["tipo"] == "atropello" for d in defectos):
            nueva = round(max(0.8, (velocidad or 1.0) - 0.05), 2)
            if nueva != velocidad:
                velocidad = nueva
                cambios.append(f"velocidad {velocidad}")
        for d in defectos:
            # un punto que no pausa se cambia por '...'; si ya eran suspensivos
            # no hay nada que reforzar y solo queda volver a tirar
            if d["tipo"] == "pausa" and d["marca"] == "." and d["orden"] not in suspensivos:
                suspensivos.add(d["orden"])
                cambios.append("suspensivos en vez de punto")
        texto = con_suspensivos(original, suspensivos)
        print("  siguiente toma: " + (", ".join(dict.fromkeys(cambios)) if cambios else "misma receta"))

    mejor = min(registro, key=lambda r: (r["gravedad"], r["intento"]))
    shutil.copyfile(mejor["archivo"], destination)
    if mejor["gravedad"]:
        print(f"AVISO: ninguna toma salio limpia; se queda el intento {mejor['intento']}, "
              f"con: {'; '.join(mejor['defectos'])}")
    elif mejor["texto"] != original:
        print(f"Se uso el texto adaptado: {mejor['texto']}")

    for r in registro:
        r["elegido"] = r["intento"] == mejor["intento"]
        r.pop("archivo")
    (out / "voz_intentos.json").write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)

    print(f"[2/4] Voz generada -> {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
