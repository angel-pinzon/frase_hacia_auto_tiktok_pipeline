# Auto TikTok Pipeline

Pipeline de código abierto para generar contenido vertical (TikTok y Reels) con avatares parlantes: extrae una frase de las letras reales de un artista con **Gemini**, la sintetiza con su voz clonada mediante **OmniVoice**, y la anima sobre una foto con **SadTalker**.

El flujo está pensado para trabajo **interactivo**: se generan varias opciones de frase, se elige, se ajusta cada video por separado y se sube a mano. La automatización total es posible pero no es el modo recomendado.

## Estructura del Proyecto

```
auto_tiktok_pipeline/
├── assets/
│   ├── DiomedesDiaz/
│   │   ├── ref_audio.wav        # Voz de referencia para clonar (5-15 s)
│   │   ├── ref_text.txt         # Transcripción del audio de referencia
│   │   └── avatar.jpg           # Foto frontal, boca cerrada
│   ├── YeisonJimenez/
│   └── VicenteFernandez/
├── lyrics/
│   ├── DiomedesDiaz/            # Una letra por archivo: titulo-en-slug.txt
│   ├── YeisonJimenez/
│   └── VicenteFernandez/
├── output/                      # Resultados (ignorado por git)
│   └── <Personaje>/             # Una carpeta por personaje, no se pisan
│       ├── script.txt           # Texto que se sintetiza
│       ├── script_meta.json     # Canción, fuente, versos y ajustes del video
│       ├── voice.wav
│       ├── video.mp4
│       ├── opciones/            # Frases de canciones conservadas
│       └── saludos/             # Saludos personalizados conservados
├── config.json                  # Configuración global y personajes
├── main.py                      # Orquestador de las cuatro fases
├── pipeline_utils.py            # Config, rutas y mezcla de ajustes
├── 1_generate_text.py           # Fase 1: frase extraída de las letras
├── 2_generate_voice.py          # Fase 2: voz clonada
├── 3_generate_video.py          # Fase 3: video vertical con texto
└── 4_upload_tiktok.py           # Fase 4: subida (opcional, sin probar)
```

## Requisitos

- **Ubuntu** (WSL2 en Windows) con GPU NVIDIA y CUDA. Probado en RTX 4060 de 8 GB.
- **FFmpeg** con `libfreetype` (para el texto en pantalla).
- **Tres entornos de Python separados**, porque sus dependencias son incompatibles entre sí:

| Entorno | Python | Para qué |
|---|---|---|
| `.venv` del proyecto | 3.12 | Orquestación, Gemini, yt-dlp |
| `~/omni_voice_project/venv` | 3.12 | OmniVoice + PyTorch 2.6 |
| `~/sadtalker_project/venv` | **3.11** | SadTalker + PyTorch 2.1.2 |

### Por qué SadTalker necesita Python 3.11

Sus dependencias están fijadas a versiones antiguas y **no funcionan en Python 3.12**:

- `numpy==1.23.4` no tiene wheel para 3.12 e intenta compilar desde fuente.
- `basicsr==1.4.2` importa `torchvision.transforms.functional_tensor`, eliminado en torchvision 0.17. Hay que quedarse en **torch 2.1.2 + torchvision 0.16.2**.
- `librosa==0.9.2` necesita `pkg_resources`, así que hace falta `setuptools<81`.
- El `imageio==2.19.3` que fija SadTalker entra en recursión infinita al escribir el vídeo: hay que **actualizarlo**.

```bash
python3.11 -m venv ~/sadtalker_project/venv
~/sadtalker_project/venv/bin/pip install torch==2.1.2 torchvision==0.16.2 \
    --index-url https://download.pytorch.org/whl/cu121
~/sadtalker_project/venv/bin/pip install -r SadTalker/requirements.txt
~/sadtalker_project/venv/bin/pip install "setuptools<81" -U imageio imageio-ffmpeg
bash SadTalker/scripts/download_models.sh     # ~2,4 GB de checkpoints
```

## Puesta en marcha

1. **Clave de Gemini** en un archivo `.env` (ignorado por git):

```bash
echo 'GEMINI_API_KEY=tu_api_key' > .env
```

2. **Letras del artista** en `lyrics/<Personaje>/`, un `.txt` por canción. **El nombre del archivo es el título** que se usa para atribuir la cita, así que debe ser correcto: `sin-medir-distancias.txt` → "Sin Medir Distancias".

3. **Audio de referencia** en `assets/<Personaje>/ref_audio.wav`: 5-15 s de habla limpia, sin música de fondo ni voces solapadas. Una entrevista funciona mucho mejor que un concierto. Para extraerlo de YouTube:

```bash
.venv/bin/yt-dlp -f bestaudio -x --audio-format wav --download-sections "*254-284" -o "ref.%(ext)s" URL
ffmpeg -i ref.wav -ac 1 -ar 24000 -af "loudnorm=I=-18:TP=-2:LRA=11" -c:a pcm_s16le assets/<Personaje>/ref_audio.wav
```

Conviene transcribir el tramo con Whisper antes de recortar, para localizar dónde habla el artista y no el entrevistador. `loudnorm` iguala el nivel a unos -18 dB de media: las fuentes flojas (-27 dB en un caso real) dan clonaciones pobres si no se normalizan.

4. **Avatar** en `assets/<Personaje>/avatar.jpg`. Frontal, **boca cerrada**, sin marcas de agua de terceros. La boca abierta degrada mucho la sincronía labial.

Sobre la resolución, lo que importa no es el tamaño absoluto sino **cuánto hay que ampliar**: del recorte 9:16 hay que llegar a 1080 px de ancho. Una foto de 1600x1754 reduce (bien); una de 639x480 amplía 4x y se ve blanda. Regla rápida: la altura de la foto debería superar los 1900 px, o su ancho recortado los 1080.

## Flujo interactivo (recomendado)

```bash
.venv/bin/python 1_generate_text.py     # propone una frase verificada
# revisar output/<Personaje>/script_meta.json, ajustar si hace falta
.venv/bin/python 2_generate_voice.py    # ~30 s
.venv/bin/python 3_generate_video.py    # ~10 min con size 512 + GFPGAN
```

Entre fases se puede editar `output/<Personaje>/script_meta.json`:

- **`verses`**: lo que se **ve** en pantalla. Los **saltos de línea** marcan cómo se reparte; la **puntuación** marca las pausas al hablar. Un punto pausa más que una coma. Se pueden combinar: acabar un verso en punto *y* dejar el salto de línea.
- **`overrides`**: ajustes que aplican **solo a este video**, mezclados sobre `config.json`.

`script.txt` es lo que se **pronuncia** y va por separado, así que se puede forzar la fonética sin ensuciar el texto visible. Ejemplo real: OmniVoice leía "Soatá" como *"Suatá"*; escribiéndolo **`So-atá`** en `script.txt` lo pronuncia bien, mientras `verses` conserva la grafía correcta. El guion separa las vocales sin añadir consonantes; `So atá` y `Sohatá` dan resultados peores.

### Saludos personalizados

El mismo pipeline sirve para encargos: se salta la Fase 1 y se escribe el texto a mano en `script.txt` y `verses`, dejando `song` vacío para que no salga el rótulo de canción. Si el texto ya termina con la coletilla del personaje, conviene anularla para que no se repita:

```json
"overrides": { "characters": { "DiomedesDiaz": { "text_suffix": "" } } }
```

### Ajustes por video

Cada frase tiene su ritmo, así que a veces hace falta afinar una sola. Ejemplo real: el TTS aceleraba tanto una sección que se comía sílabas.

```json
{
  "song": "La Plata",
  "verses": "Pero me doy cuenta que la vida es un sueño.\nY antes de morir, es mejor aprovecharla",
  "overrides": {
    "omnivoice": { "speed": 0.85 },
    "video": { "text": { "size": 42 } }
  }
}
```

La mezcla es recursiva: solo se pisa lo que se nombra, el resto de `config.json` se conserva. Ojo, **volver a ejecutar la Fase 1 reescribe `script_meta.json`** y se pierden los `overrides`.

## Las cuatro fases

### Fase 1 — Frase extraída de las letras (`1_generate_text.py`)

Elige una canción al azar, le pasa la letra completa a Gemini y le pide **un fragmento textual** que funcione como frase motivadora. No inventa nada: cita.

Tres garantías **en código**, no confiadas al prompt:

- **Verificación literal**: el fragmento debe existir en la letra, comparando sin tildes, mayúsculas ni puntuación. Si el modelo parafrasea o cose versos separados, se descarta.
- **Mínimo de palabras** (`gemini.min_words`, 14): evita clips de 3-4 s, que rinden mal en TikTok.
- **Reintentos ante saturación**: los errores 429/500/502/503 de la API se reintentan con espera progresiva; los demás se propagan.

Si una canción no da un fragmento válido, prueba con otra hasta `gemini.max_attempts`.

Con `top_songs` se restringe a los éxitos, que es lo que el público reconoce. Con la lista vacía usa todo el corpus.

### Fase 2 — Voz clonada (`2_generate_voice.py`)

Sintetiza con OmniVoice usando el audio de referencia del personaje.

OmniVoice tiene **dos defectos aleatorios**, y ambos se corrigen regenerando hasta que el audio pase los controles (`max_attempts`):

**1. Corta la última palabra a media sílaba.** Dos defensas:

- **Coletilla** (`text_suffix`, definida **por personaje**): un cierre en carácter que absorbe el corte. Si algo se trunca, es la coletilla, nunca el verso. Diomedes cierra con `". Con mucho Gusto"` y Yeison con `". Con el Corazón"`. Si el personaje no define ninguna, se usa la global de `omnivoice`.
- **Medición de la cola**: un final natural decae hacia el silencio; un corte en seco deja energía alta. Si supera `cut_threshold`, se regenera.

**2. Atropella palabras sueltas**, comprimiéndolas hasta hacerlas ininteligibles. Se detecta transcribiendo con Whisper y midiendo la duración de cada palabra: si alguna baja de `min_word_duration` (0.13 s), se regenera. Añade unos 6 s por intento. Si el problema persiste en una frase concreta, bajar `omnivoice.speed` a 0.85-0.9 suele arreglarlo; es un ajuste típico de `overrides`.

Detalles que costó descubrir:

- `--language Spanish` **importa**: sin él, la misma frase pasó de 63 a 763 de nivel de corte.
- Los signos de exclamación en la coletilla **empeoran** el cierre.
- Sin `--ref_text`, OmniVoice transcribe el audio de referencia con Whisper en cada ejecución. Cuesta unos segundos, pero es más fiable que darle una transcripción dudosa.

### Fase 3 — Video vertical (`3_generate_video.py`)

SadTalker anima el rostro; FFmpeg encuadra y rotula.

- **Recorte a la cara**: la foto suele ser apaisada y el destino es 9:16. Sin recortar, el 62 % del video son barras negras. Se detecta la cara y se recorta una franja 9:16 centrada en ella.
- **La cara se detecta en el render, no en la foto original**: con `--size 512` SadTalker devuelve el doble de resolución que la entrada, así que las coordenadas de la foto no valen.
- **Detector RetinaFace**, con Haar como respaldo. Haar fallaba con cabezas inclinadas y con sombreros que sombrean la frente — con las fotos de charro no encontraba nada y el encuadre caía a barras negras. RetinaFace ya viene instalado con GFPGAN.
- **Reducción automática del avatar** (`max_source`, 1600 px): con imágenes muy grandes el detector de puntos faciales de SadTalker revienta con un error críptico de OpenCV. El archivo original no se toca.
- **Texto en pantalla**: los versos sobre un oscurecido inferior y el título de la canción en dorado. Mucha gente ve TikTok sin sonido.

### Realismo

`still: true` congela la cabeza y es la principal causa de que el resultado parezca un muñeco. Medido sobre el mismo audio, quitarlo **multiplica por 2.4 el movimiento**:

| Ajuste | Movimiento medio |
|---|---|
| `still: true`, expresión 1.0 | 0.30 |
| `still: false` | 0.73 |
| `still: false`, expresión 1.3 | 0.68 |
| `still: false`, expresión 1.6, pose 16 | 1.00 |

Por defecto queda `still: false` con `expression_scale: 1.3`. Subir mucho la expresividad tiende a exagerar la boca hasta la caricatura. Con movimiento de cabeza el video puede durar algo más que el audio, porque SadTalker añade fotogramas de movimiento residual al final.

`size: 512` + `enhancer: gfpgan` da la mejor calidad pero sube el render a ~10 min. Con `size: 256` y sin enhancer baja a menos de un minuto, útil para iterar y para comparar ajustes.

### Fase 4 — Subida a TikTok (`4_upload_tiktok.py`)

Automatiza el navegador con Playwright. **Sin probar y con `dry_run: true`.** El flujo recomendado es subir a mano: los selectores de TikTok cambian sin aviso y no compensa depurar un scraper mientras el formato aún se está afinando.

## Configuración (`config.json`)

| Clave | Qué hace |
|---|---|
| `active_character` | Personaje en uso |
| `characters.<id>.top_songs` | Restringe a los éxitos; vacío usa todo el corpus |
| `characters.<id>.text_suffix` | Coletilla propia del personaje; manda sobre la global |
| `gemini.min_words` | Mínimo de palabras del fragmento (14) |
| `gemini.max_attempts` | Canciones a probar antes de rendirse (5) |
| `gemini.api_retries` | Reintentos ante saturación de la API (4) |
| `omnivoice.text_suffix` | Coletilla de respaldo si el personaje no define la suya |
| `omnivoice.cut_threshold` | Energía final máxima antes de regenerar (250) |
| `omnivoice.min_word_duration` | Duración mínima por palabra antes de regenerar (0.13 s) |
| `omnivoice.speed` | Ritmo del habla; bajar a 0.85-0.9 si atropella sílabas |
| `video.size` | 256 rápido, 512 mejor calidad |
| `video.enhancer` | `gfpgan` o vacío |
| `video.still` | `true` congela la cabeza; `false` da realismo |
| `video.expression_scale` | Expresividad facial (1.3); pasado de 1.5 caricaturiza |
| `video.pose_style` | Estilo de movimiento de cabeza, 0-45 |
| `video.max_source` | Lado mayor al que se reduce el avatar (1600 px) |
| `video.crop_to_face` | Recorte 9:16 centrado en la cara |
| `video.text.*` | Fuente, tamaño, ancho de línea, oscurecido y posición |

## Añadir un personaje

1. `assets/<Id>/` con `ref_audio.wav` y `avatar.jpg`.
2. `lyrics/<Id>/` con las letras, **nombradas con el título de la canción**.
3. Entrada en `characters` de `config.json`, con su `prompt` y `top_songs`.
4. Cambiar `active_character`.

## Consideraciones legales

Esto genera **video sintético realista de personas reales**. Antes de publicar:

- TikTok exige **etiquetar** el contenido generado por IA que muestra personas reales.
- Con un artista **vivo** el riesgo no es solo reputacional: hay derechos de imagen y voz que puede reclamar directamente.
- Citar **versos con atribución** es terreno mucho más seguro que ponerle frases inventadas en la boca.
- Las fotos de prensa y las letras tienen derechos de autor propios.
