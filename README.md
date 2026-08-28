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
├── guiones/                     # Diálogos generados (texto propio, versionado)
├── prompts/                     # Prompt de avatares y fichas de escenas
├── output/escenas/              # Clips de Veo cacheados (pesados, no versionados)
├── output/dialogos/             # Montajes multi-personaje
├── config.json                  # Configuración global y personajes
├── main.py                      # Orquestador de las cuatro fases
├── pipeline_utils.py            # Config, rutas y mezcla de ajustes
├── 1_generate_text.py           # Fase 1: frase extraída de las letras
├── 2_generate_voice.py          # Fase 2: voz clonada
├── 3_generate_video.py          # Fase 3: video vertical con texto
├── 3b_add_scenes.py             # Fase 3b: escenas con Veo (opcional)
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

La Fase 3 cuesta unos 10 minutos de GPU, así que **todo se valida antes de renderizar**. El orden real de trabajo es este:

**1. Elegir personaje.** Cambiar `active_character` en `config.json`. Cada uno escribe en su propia carpeta de `output/`, así que no se pisan.

**2. Pedir varias frases y escoger.** En lugar de aceptar la primera, conviene generar tres candidatas de canciones distintas y comparar. Cada una llega ya verificada contra su letra:

```bash
.venv/bin/python 1_generate_text.py     # una propuesta
```

Para tres de un tirón se ejecuta la Fase 1 varias veces, o se recorren varias canciones reutilizando `load_songs()`, `ask_gemini()` e `is_verbatim()` del módulo. Se comparan por longitud, por si el mensaje se entiende fuera de contexto y por lo reconocible que sea la canción.

**3. Ajustar el texto a mano si hace falta.** Es habitual alargar la frase con los versos siguientes o cambiar la puntuación. **Si se edita a mano se pierde la garantía automática de la Fase 1**, así que hay que volver a verificar contra la letra antes de seguir:

```python
m1.is_verbatim(texto, m1.clean_lyrics(open(ruta_letra).read()))
```

**4. Generar solo la voz y escucharla.** Es el paso que ahorra tiempo: unos 30 segundos frente a los 10 minutos del render.

```bash
.venv/bin/python 2_generate_voice.py
```

Si el resultado no convence, se ajusta y se repite. Los defectos típicos y su arreglo están en la Fase 2. **Nunca llamar a OmniVoice directamente para probar variantes**: se saltan los controles de calidad y el audio sale con la última sílaba cortada sin que nadie avise.

**5. Renderizar el video.**

```bash
.venv/bin/python 3_generate_video.py
```

**6. Archivar el resultado**, porque `video.mp4` y `voice.wav` se sobrescriben en la siguiente ejecución. Por convención:

- `output/<Personaje>/opciones/` — frases sacadas de canciones
- `output/<Personaje>/saludos/` — felicitaciones y encargos
- `output/<Personaje>/frases/` — frases sueltas y bromas

Se guarda el `.mp4`, el `.wav` y el `.json`, con el nombre de la canción o del destinatario.

### Afinar la entonación

Cuando una frase no suena como se quiere, se prueban variantes de puntuación y se mide en vez de decidir a oído. Dos ejemplos reales:

- Dos preguntas seguidas sonaban como una sola. Separándolas con **puntos suspensivos** (`¿Qué?... ¿Pola o miedo?`) la pausa pasó de 0.13 s a 0.49 s, y Whisper empezó a transcribirlas como dos preguntas distintas. Con punto simple, en cambio, el modelo entendía mal una palabra.
- Un topónimo mal pronunciado se corrigió con un guion, sin tocar el texto en pantalla.

Para comparar variantes: generarlas, transcribirlas con Whisper y medir las pausas con `silencedetect`. Después **regenerar la elegida por el pipeline**, para que pase por los controles.

Entre fases se puede editar `output/<Personaje>/script_meta.json`:

- **`verses`**: lo que se **ve** en pantalla. Los **saltos de línea** marcan cómo se reparte; la **puntuación** marca las pausas al hablar. Un punto pausa más que una coma. Se pueden combinar: acabar un verso en punto *y* dejar el salto de línea.
- **`overrides`**: ajustes que aplican **solo a este video**, mezclados sobre `config.json`.

`script.txt` es lo que se **pronuncia** y va por separado, así que se puede forzar la fonética sin ensuciar el texto visible. Ejemplo real: OmniVoice leía "Soatá" como *"Suatá"*; escribiéndolo **`So-atá`** en `script.txt` lo pronuncia bien, mientras `verses` conserva la grafía correcta. El guion separa las vocales sin añadir consonantes; `So atá` y `Sohatá` dan resultados peores.

### Modo libre: texto original al estilo del personaje

Además de citar versos, la Fase 1 puede **escribir** frases nuevas imitando la forma de hablar del artista, para videos más largos de tono optimista o costumbrista:

```bash
.venv/bin/python 1_generate_text.py --libre
```

Toma varias letras suyas como referencia de vocabulario y giros, y redacta un texto original de 40-70 palabras. Requiere un `prompt_libre` en la ficha del personaje.

**La diferencia de fondo con el modo cita:** aquí no hay nada que verificar contra una fuente, porque el texto es inventado. Dos decisiones de diseño lo compensan:

- **No se atribuye ninguna canción.** `song` queda vacío, así que no sale rótulo y el video no presenta como cita algo que no lo es. En `context_songs` queda registrado qué letras se usaron de referencia.
- **Se comprueba lo contrario que en el modo cita**: que ninguna línea sea textual de las letras. Si el modelo copia un verso pese a la prohibición, se descarta y reintenta. Sin ese control existe el riesgo de publicar un verso real como si fuera texto propio.

Ajustes en `gemini`: `context_songs` (cuántas letras de referencia), `free_min_words` y `free_max_words`.

Ten en cuenta dos consecuencias de los textos largos: el render crece en proporción —GFPGAN procesa fotograma a fotograma, así que 30 s pueden rondar la media hora— y el texto en pantalla, que hoy es estático, deja de caber. Para esas duraciones harían falta subtítulos sincronizados, que aún no están implementados.

### Saludos personalizados

El mismo pipeline sirve para encargos: se salta la Fase 1 y se escribe el texto a mano en `script.txt` y `verses`, dejando `song` vacío para que no salga el rótulo de canción. Si el texto ya termina con la coletilla del personaje, conviene anularla para que no se repita:

```json
"overrides": { "characters": { "DiomedesDiaz": { "text_suffix": "" } } }
```

### Ajustes por video

Cada frase tiene su ritmo, así que a veces hace falta afinar una sola. Ejemplo real: el TTS aceleraba tanto una sección que se comía sílabas.

```json
{
  "song": "Título de la canción",
  "verses": "Primer verso.\nSegundo verso.",
  "overrides": {
    "omnivoice": { "speed": 0.85, "max_attempts": 6 },
    "video": { "text": { "size": 42 } }
  }
}
```

La mezcla es recursiva: solo se pisa lo que se nombra, el resto de `config.json` se conserva. Ojo, **volver a ejecutar la Fase 1 reescribe `script_meta.json`** y se pierden los `overrides`.

Los valores que funcionaron quedan guardados en el `.json` archivado, así que conviene consultarlos al hacer otro video parecido. Ajustes que se repiten:

| Síntoma | Ajuste |
|---|---|
| Atropella palabras cortas | `speed` 0.85-0.9 |
| Frase corta que se corta al final | `max_attempts` 6-10, y coletilla en el personaje |
| Verso largo que se parte en pantalla | `video.text.max_chars` y `size` |

El rótulo de la canción sale de `song`, no del nombre del archivo. Si la letra viene de una colaboración (`...-part-otro-artista.txt`), conviene poner en `song` solo el título limpio; el campo `source` conserva la ruta real y con ella la trazabilidad.

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

### Fase 3b — Escenas generadas (`3b_add_scenes.py`, opcional)

El retrato fijo hablando se hace monótono. Esta fase sustituye parte del video por una **escena generada con Veo**, mientras la voz clonada sigue por debajo: el avatar establece quién habla durante unos segundos y luego la imagen pasa a ilustrar lo que dice.

```bash
.venv/bin/python 3b_add_scenes.py     # despues de la fase 3
```

El prompt de la escena **se deriva del propio texto**: Gemini lee los versos y escribe la descripción, así que no hay que redactar nada. El resultado va a `video_escena.mp4`, dejando intacto el `video.mp4` original.

**Por qué texto a video y no imagen a video.** Veo rechaza las imágenes de entrada que contienen personas reconocibles: *"we can't create videos from input images containing celebrity or their likenesses"*. Por eso no se puede animar el avatar en una escena real. Lo que sí funciona es generar escenas con **gente anónima o solo paisaje**, y el prompt incluye esa instrucción explícita.

**Coste y límites.** Cada clip son 8 segundos y cuesta unos $0.24 con el modelo Lite. Requiere **facturación activada** en el proyecto de Google Cloud: el plan gratuito da cuota cero para video e imagen. Lo más seguro es comprar saldo prepago **con la recarga automática desactivada**, que actúa como tope real de gasto — un presupuesto de Cloud solo avisa, no detiene nada.

Las escenas se cachean en `output/escenas/` con el prompt en un `.json` al lado: repetir un prompt no se vuelve a pagar, y un resultado bueno se puede reproducir.

**Dos costuras conocidas.** Veo entrega 720x1280 y hay que ampliar a 1080x1920, así que la escena se ve algo más blanda que el avatar. Y si el audio dura más que los 8 segundos del clip, se congela el último fotograma; el módulo avisa por consola cuántos segundos quedan congelados. Para textos largos conviene subir `corte_s` o generar dos escenas.

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
| `escenas.model` | Modelo de Veo; el Lite es el más barato |
| `escenas.corte_s` | Segundos de avatar antes de pasar a la escena (4.0) |
| `escenas.duracion_clip_s` | Duración del clip que devuelve Veo, para avisar del congelado |

## Particularidades de cada personaje

Cada voz y cada foto tienen sus manías. Lo que costó descubrir, para no repetirlo:

### Diomedes Díaz

- **Coletilla `". Con mucho Gusto"`**, que era muletilla suya real. Funciona doblemente: da identidad al cierre y absorbe el truncado.
- **`speed` 0.9**. Atropella palabras átonas cortas —"pero", "sido"— hasta hacerlas ininteligibles. Con velocidad normal falló los tres intentos; con 0.9 salió a la primera.
- **Dos avatares disponibles.** El de estudio generado con IA rinde bastante mejor que la foto original con acordeón: boca cerrada y solo 1.15x de ampliación frente a 1.80x. La foto original aporta más contexto vallenato, así que sirve para rotar.
- Sus mayores éxitos estaban entre los archivos **sin título** del corpus original. Al descartarlos por no poder atribuirlos, se perdían sus tres canciones más escuchadas; hubo que recuperarlos identificándolos por el estribillo.

### Yeison Jiménez

- **Coletilla `". Con el Corazón"`**, título de una de sus canciones.
- No necesita ajuste de velocidad en general, aunque alguna toma suelta atropella una palabra y se regenera sola.
- Su avatar de 2804x3737 **reventaba el detector de puntos faciales** de SadTalker con un error críptico de OpenCV. De ahí salió la reducción automática por `max_source`.

### Vicente Fernández

- **Sin coletilla definida.** Es una carencia: sin escudo, el truncado muerde la última palabra del verso y hay que confiar solo en los reintentos.
- Su audio de referencia venía **muy bajo, a -27 dB de media**, casi 10 dB por debajo de lo normal. Sin `loudnorm` la clonación sale pobre.
- Su corpus es **casi todo colaboraciones** (`...-part-otro-artista.txt`), así que el rótulo hay que limpiarlo a mano en `song`. Y solo 6 de sus 15 canciones más escuchadas están presentes: faltan varios de sus clásicos en solitario.
- Su foto con sombrero **dejaba ciego al detector Haar**, porque el ala sombrea la frente. Fue el caso que motivó cambiar a RetinaFace.

### Rafael Poveda

- **No es cantante**: sin letras, sin `prompt` y sin `top_songs`. Funciona solo con texto escrito a mano.
- **Coletilla `" ¿Eh?"`**, añadida precisamente porque sin ella las frases cortas se cortaban una y otra vez. Pasamos de cuatro rondas peleando con umbrales a resolverlo en dos intentos.
- Para frases de pocos segundos: **`speed` 0.8 y `max_attempts` 8-10**. Es el peor caso del pipeline.
- Su audio sale de un podcast **de entrevistas**, así que hay que transcribir con marcas de tiempo y elegir tramos donde hable él y no su invitado.
- Su avatar está **generado con IA** y lleva marca de agua visible, que acaba en todos los videos.

### Pronunciación: casos resueltos

`script.txt` es lo que se pronuncia y `verses` lo que se ve, así que la fonética se fuerza sin ensuciar el texto en pantalla:

| Se escribía | Sonaba | Solución |
|---|---|---|
| Soatá | "Suatá" | `So-atá` — el guion separa las vocales |
| ¿Qué? ¿Pola...? | una sola pregunta | `¿Qué?... ¿Pola` — los suspensivos separan |
| Wiliam | "William", a la inglesa | escribirlo fonéticamente |

## Añadir un personaje

1. `assets/<Id>/` con `ref_audio.wav` y su avatar.
2. `lyrics/<Id>/` con las letras, **nombradas con el título de la canción**.
3. Entrada en `characters` de `config.json`, con su `prompt`, su `top_songs` y su `text_suffix`.
4. Cambiar `active_character`.

Para llenar `top_songs` conviene mirar los datos reales de reproducciones —kworb publica los de Spotify— en vez de fiarse de la memoria, y comprobar cuáles de esas canciones están en el corpus.

**Personajes sin canciones.** No todos son cantantes: `RafaelPoveda` es un periodista, así que su `lyrics_dir`, `prompt` y `top_songs` van vacíos. Funciona solo con las fases 2 y 3, escribiendo el texto a mano. Un personaje así **necesita coletilla igualmente**, porque sin ella el truncado muerde la última palabra del contenido: sin canciones que citar, las frases suelen ser cortas, y ahí el corte es más probable.

**Avatares generados con IA.** Cuando no hay una foto buena —frontal, boca cerrada, resolución suficiente— se puede transformar una existente con un modelo de imagen. Funciona bien pidiendo explícitamente que conserve los rasgos, la edad y el peinado, con fondo liso y encuadre vertical 9:16. Dos avisos: estos modelos tienden a **rejuvenecer y alisar la piel**, así que hay que elegir por parecido y no por belleza; y algunos dejan una **marca de agua** que acabará en todos los videos, lo que puede ser un problema o una ventaja según cómo quieras señalar que el contenido es generado.

## Consideraciones legales

Esto genera **video sintético realista de personas reales**. Antes de publicar:

- TikTok exige **etiquetar** el contenido generado por IA que muestra personas reales.
- Con un artista **vivo** el riesgo no es solo reputacional: hay derechos de imagen y voz que puede reclamar directamente.
- Citar **versos con atribución** es terreno mucho más seguro que ponerle frases inventadas en la boca.
- Las fotos de prensa y las letras tienen derechos de autor propios.
