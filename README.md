# Auto TikTok Pipeline

Pipeline de código abierto para generar contenido vertical (TikTok y Reels) con avatares parlantes: extrae una frase de las letras reales de un artista con **Gemini**, la sintetiza con su voz clonada mediante **OmniVoice**, y la anima sobre una foto con **SadTalker**.

El flujo está pensado para trabajo **interactivo**: se generan varias opciones de frase, se elige, se ajusta cada video por separado y se sube a mano. La automatización total es posible pero no es el modo recomendado.

## Retomar el trabajo

Punto de entrada para continuar en otra sesión sin depender del historial de conversación. El resto del README es referencia.

### Qué hay en marcha

| Línea | Estado | Dónde mirar |
|---|---|---|
| Videos de artistas: frases, monólogos, diálogos | estable, se produce a demanda | este README |
| Saludos personalizados | a demanda; los últimos, para Wilmer Cortez y Ticor | `output/DiomedesDiaz/saludos/` |
| Serie *Algo pasa en Soatá* | temporada completa, publicada | [serie_soata/README.md](serie_soata/README.md), tabla *Dónde va la temporada* |
| Serie del celador, en Bogotá, con Grok Imagine | capítulos 1-4 terminados, de 7 | [serie_celador/README.md](serie_celador/README.md) |

Lo último que se hizo: `git log --oneline -15`. Cada mensaje explica el porqué del cambio, no solo el qué.

### Dónde vive el estado

- **Texto y decisiones, versionados**: `guiones/`, `prompts/escenas/` —una ficha JSON por capítulo con sus notas, lecciones y comando de montaje—, `serie_soata/README.md` y `serie_celador/README.md`.
- **Medios, solo en disco**: `output/` (voces, videos, clips de Veo) y `assets/` (audios de referencia, avatares y fotos de locaciones). Los videos se pueden regenerar; **las fotos de `assets/` no**, así que conviene tener copia fuera del repo.
- **Personaje activo**: `active_character` en `config.json`, que queda en `YeisonJimenez`. Un encargo de otro personaje lo cambia y **lo restaura al terminar**, para que el repo quede limpio.
- **Remoto**: `github.com/angel-pinzon/frase_hacia_auto_tiktok_pipeline`. Se sube solo cuando se pide.
- **Instalación en otra máquina**: [INSTALACION.md](INSTALACION.md). Un clon llega sin letras, audios, avatares ni fotos.

### Qué se pide y qué significa

| Petición | Cadena |
|---|---|
| una frase de un artista | Fase 1 → 2 → 3 → 3c |
| **"completo"** | Fase 1 → 2 → 3 → 3c → 3b, la de mayor calidad, con escena de Veo |
| un saludo de cumpleaños | texto a mano → 2 → 3 → 3c, sin escena. Ver [Saludos personalizados](#saludos-personalizados) |
| un capítulo de una serie con Veo | `serie_generar.py` → revisión → `serie_placas.py`. Ver [Video generado con Veo](#video-generado-con-veo-serie_generarpy-serie_placaspy) |
| un capítulo de la serie del celador | `serie_imagenes.py` para las imágenes → `serie_generar.py` acto a acto → `serie_placas.py --encima`. Ver [Serie con Grok Imagine](#serie-con-grok-imagine-serie_imagenespy-imagenpy) |

### Forma de trabajo

- **El texto se valida antes de generar.** Se propone, se espera el visto bueno y solo entonces se gasta GPU o cuota.
- **Un resultado no está bueno hasta que lo ve una persona.** La revisión automática —medir brillo, ampliar fotogramas, transcribir— atrapa defectos técnicos, pero ha dejado pasar edificios inventados, efectos de aspecto barato y pausas que faltaban, y fue la revisión humana la que los detectó. Al entregar, describir qué se midió y qué preocupa, sin calificarlo.
- **Antes de gastar varias generaciones de Veo, se prueba un acto** y se enseña.
- **Se mide en vez de suponer**: la energía del final para los cortes, `silencedetect` para las pausas, `signalstats` para la luz.

### Trampas operativas

- **Procesos largos en segundo plano**: lanzarlos con `setsid nohup ... &` y pararlos con `kill -TERM -<PGID>`. SadTalker y MuseTalk corren como subprocesos en sus propios entornos, y un `kill` al proceso principal los deja vivos ocupando la GPU.
- **`pkill -f` y `pgrep -f` pueden matar su propia shell**: si el patrón aparece en la línea de comandos que los lanza, se encuentran a sí mismos y la shell muere con código 144. Usar el PID, o el truco `grep "[s]adtalker"`.
- **Nada reutilizable en el directorio temporal de la sesión**: se borra al cerrarla. `serie_generar.py` y `revisar_voz.py` se reconstruyeron varias veces antes de pasar al repo.
- **Cuota de Veo**: 10 generaciones al día, que se renuevan a las 3 de la madrugada en Colombia. Una petición cancelada a medias probablemente ya contó. Hay que llevar la cuenta durante la sesión.
- **Antes de sobrescribir `output/<Personaje>/`**, comprobar que lo que hay está archivado en `opciones/` o `saludos/`. Si no lo está, apartarlo a `_previo_<nombre>/`.

### Pendiente

- **La Fase 3b ignora el lipsync**: toma `video.mp4` en vez de `video_lipsync.mp4`. Ver *Arquitectura*.
- Vicente Fernández sigue sin coletilla.
- Los diálogos multipersonaje de `output/dialogos/` se montaron con scripts que no llegaron al repo. Si se hace otro, conviene convertirlo en herramienta.

## Arquitectura

La plataforma tiene **tres capas** —orquestación, motores locales y servicios en la nube— y un contrato muy simple entre ellas: **cada fase lee y escribe archivos en `output/<Personaje>/`**. No hay base de datos, ni servidor, ni datos compartidos en memoria.

### Videos de artistas

```mermaid
flowchart TD
    CFG["config.json<br/>+ overrides de script_meta.json"]
    LY["lyrics/Personaje/"]
    AV["assets/Personaje/<br/>ref_audio.wav · avatar"]

    F1["Fase 1 · 1_generate_text.py"]
    F2["Fase 2 · 2_generate_voice.py"]
    F3["Fase 3 · 3_generate_video.py"]
    F3c["Fase 3c · 3c_lipsync.py"]
    F3b["Fase 3b · 3b_add_scenes.py"]

    GEM(["Gemini · nube"])
    VEO(["Veo · nube"])
    OMNI[["OmniVoice + Whisper<br/>entorno omni_voice · Py 3.12"]]
    SAD[["SadTalker + GFPGAN + RetinaFace<br/>entorno sadtalker · Py 3.11"]]
    MUSE[["MuseTalk<br/>entorno musetalk · Py 3.11"]]
    FF[["FFmpeg"]]

    LY --> F1
    F1 <--> GEM
    F1 -->|"script.txt<br/>script_meta.json"| F2
    AV --> F2
    F2 <--> OMNI
    F2 -->|voice.wav| F3
    AV --> F3
    F3 <--> SAD
    F3 <--> FF
    F3 -->|video.mp4| F3c
    F3c <--> MUSE
    F3c --> L["video_lipsync.mp4"]
    F3 -->|video.mp4| F3b
    F3b <--> GEM
    F3b <--> VEO
    F3b <--> FF
    F3b --> E["video_escena.mp4"]
    CFG -.-> F1 & F2 & F3 & F3c & F3b
```

### Series por capítulos

El mismo camino sirve para los dos motores: `serie_generar.py` elige Veo o Grok según el
modelo que declare la ficha. Con Grok hay un paso más antes, el de las imágenes de partida.

```mermaid
flowchart LR
    FOTO["assets/<br/>foto de la locación"]
    IMG["serie_imagenes.py<br/>(solo con Grok)"]
    FICHA["prompts/escenas/<ficha>.json<br/>ficha del capítulo"]
    GEN["serie_generar.py"]
    MOD(["Veo o Grok · nube<br/>imagen a video"])
    ESC["clips de cada acto<br/>y secuencia unida"]
    PLA["serie_placas.py"]
    FF[["FFmpeg"]]
    SER["capítulo terminado<br/>+ versión vertical"]

    FOTO --> IMG
    IMG -->|"imagen editada:<br/>noche, sin gente"| GEN
    FOTO --> GEN
    FICHA --> GEN
    GEN <-->|"acto a acto"| MOD
    GEN --> ESC
    ESC --> PLA
    PLA <--> FF
    PLA --> SER
```

### Las tres capas

| Capa | Qué contiene | Dónde corre |
|---|---|---|
| **Orquestación** | Las fases (`1_` a `4_`, `3b_`, `3c_`), `main.py`, `serie_generar.py`, `serie_placas.py` y `pipeline_utils.py` | `.venv` del proyecto, Python 3.12, sin GPU |
| **Motores locales** | OmniVoice y Whisper (voz y transcripción); SadTalker, GFPGAN y RetinaFace (animación y cara); MuseTalk (labios) | Un entorno aislado cada uno, en la GPU |
| **Servicios en la nube** | Gemini (texto y prompts de escena) y Veo (video), a través de `google-genai` con `GEMINI_API_KEY` | API de Google, con coste y cuota |
| **Herramientas del sistema** | FFmpeg para recortar, rotular, montar y medir (`signalstats`, `silencedetect`, `cropdetect`); Playwright para la Fase 4 | Sistema operativo |

Los scripts de orquestación **nunca importan un motor**. Construyen una orden con el Python del otro entorno —las rutas están en `config.json`: `omnivoice.python`, `video.python`, `lipsync.python`— y la ejecutan con `subprocess`. Cuando solo necesitan un trozo de un motor, le pasan un script corto con `python -c`: la Fase 2 comprueba el ritmo con Whisper dentro del entorno de OmniVoice, y la Fase 3 detecta la cara con RetinaFace dentro del de SadTalker.

Eso tiene dos consecuencias prácticas. Un fallo del motor llega como un error del subproceso, no como una excepción de Python legible. Y **matar la fase no mata el motor**: SadTalker o MuseTalk siguen vivos ocupando la GPU, que es por lo que los procesos largos se lanzan en su propio grupo (ver *Trampas operativas*).

### El contrato entre fases: los archivos

| Fase | Lee | Escribe |
|---|---|---|
| 1 · texto | `lyrics/`, `config.json` | `script.txt`, `script_meta.json` |
| 2 · voz | `script.txt`, `ref_audio.wav` | `voice.wav` |
| 3 · retrato | `voice.wav`, avatar, `verses` de `script_meta.json` | `video.mp4` |
| 3c · labios | `video.mp4`, `voice.wav` | `video_lipsync.mp4` |
| 3b · escena | `video.mp4`, `voice.wav`, `verses` | `video_escena.mp4`, clip en `output/escenas/` |

Todo en `output/<active_character>/`. De ahí sale la forma de trabajar: **se puede parar entre dos fases, revisar, editar el archivo a mano y relanzar solo la siguiente**, sin repetir lo anterior. La contrapartida es que cada ejecución sobrescribe su archivo, así que lo bueno hay que archivarlo en `opciones/` o `saludos/`.

`main.py` encadena solo las fases 1, 2, 3 y 4 en línea recta, y casi no se usa: el trabajo real es interactivo y fase a fase. Las fases 3b y 3c se lanzan a mano.

**Incoherencia conocida:** la Fase 3b toma `video.mp4`, no `video_lipsync.mp4`. Si se ejecuta 3 → 3c → 3b, la escena final lleva los labios de SadTalker y no los de MuseTalk. Para que la escena incluya el lipsync, hoy hay que copiar `video_lipsync.mp4` sobre `video.mp4` antes de lanzar la 3b.

### La configuración en capas

Al arrancar, cada fase llama a `load_config()`, que monta la configuración en tres pasos:

1. **`config.json`**: los valores globales y la ficha de cada personaje.
2. **`active_character`**: decide qué personaje se usa y en qué carpeta de `output/` se lee y escribe.
3. **`overrides` de `script_meta.json`**: se mezclan de forma recursiva sobre lo anterior con `deep_merge()`. Solo se sustituye lo que se nombra, y afectan únicamente al video que está en esa carpeta.

Así, un ajuste que solo sirve para una frase —`speed`, `max_attempts`, tamaño de letra— va con esa frase y no toca la configuración global.

### Por qué está hecho así

- **Entornos aislados** porque las dependencias son incompatibles: SadTalker necesita numpy 1.23 y torch 2.1; MuseTalk, torch 2.0 y una pila mmcv que no convive con nada más. Ver *Requisitos*.
- **Archivos como contrato** para poder trabajar de forma interactiva: cada paso se revisa y se corrige a mano antes de gastar los minutos de GPU del siguiente.
- **Los controles van en el código, no en el prompt**: la cita textual de la Fase 1, la detección de cortes y de palabras atropelladas de la Fase 2, el mínimo de brillo y el bloqueo de fichas `PENDIENTE` de la serie. El modelo puede ignorar una instrucción; una comprobación no.
- **Caché de Veo por hash del prompt** en la Fase 3b: repetir una escena no se vuelve a pagar.

## Estructura del Proyecto

```
auto_tiktok_pipeline/
├── assets/                      # Imagenes y audios: ignorados por git, sin copia
│   ├── DiomedesDiaz/            # Igual para YeisonJimenez, VicenteFernandez, RafaelPoveda
│   │   ├── ref_audio.wav        # Voz de referencia para clonar (5-15 s)
│   │   ├── ref_text.txt         # Transcripción del audio de referencia (versionada)
│   │   └── avatar*.png|jpg      # El que se usa lo fija image_path en config.json
│   ├── iglesia_soata*.jpg       # Locaciones de la serie: la plaza y la iglesia
│   ├── ParqueJuanJoseRondon.jpg # Parque del camino (capítulo 3)
│   ├── parque_soata1.jpg        # Parque de las piedras talladas (capítulo 4)
│   └── cupula_soata.jpg         # Cúpula desde el aire (capítulo 7)
├── lyrics/<Personaje>/          # Una letra por archivo: titulo-en-slug.txt
├── guiones/                     # Diálogos y monólogos escritos (versionado)
├── prompts/
│   ├── avatar.txt               # Prompt para generar avatares
│   └── escenas/                 # Fichas de escenas de Veo y de capítulos de la serie
├── serie_soata/README.md        # "Algo pasa en Soatá": historia, arco, estado y lecciones de Veo
├── serie_celador/               # Segunda serie, en Bogotá, con Grok Imagine
│   ├── README.md                # Historia, trama, costes y todo lo aprendido con Grok
│   ├── assets/                  # Fotos de las locaciones y sus versiones editadas (ignorado)
│   ├── personaje/               # Hoja de referencia del celador (ignorado)
│   ├── figura/                  # Hoja de referencia de la estatua de bronce (ignorado)
│   ├── output/                  # Clips y capítulos terminados (ignorado)
│   └── facebook/                # Versiones para Reels y sus descripciones (ignorado)
├── output/                      # Resultados, ignorado por git
│   ├── <Personaje>/             # Una carpeta por personaje, no se pisan
│   │   ├── script.txt           # Lo que se pronuncia
│   │   ├── script_meta.json     # Lo que se ve (verses), canción, fuente y overrides
│   │   ├── voice.wav, video.mp4, video_lipsync.mp4, video_escena.mp4
│   │   ├── opciones/            # Frases y monólogos terminados
│   │   ├── saludos/             # Saludos terminados: <destinatario>.mp4/.wav/.json
│   │   └── _previo_<nombre>/    # Lo apartado antes de sobrescribir
│   ├── escenas/                 # Clips de Veo, crudos y cacheados
│   ├── dialogos/                # Montajes multipersonaje
│   └── serie/                   # Capítulos terminados; pruebas/ guarda las versiones descartadas
├── config.json                  # Configuración global y personajes
├── main.py                      # Orquestador de las cuatro fases
├── pipeline_utils.py            # Config, rutas y mezcla de ajustes
├── 1_generate_text.py           # Fase 1: frase extraída de las letras
├── 2_generate_voice.py          # Fase 2: voz clonada
├── 3_generate_video.py          # Fase 3: video vertical con texto
├── 3b_add_scenes.py             # Fase 3b: escenas con Veo (opcional)
├── 3c_lipsync.py                # Fase 3c: boca rehecha con MuseTalk (opcional)
├── 4_upload_tiktok.py           # Fase 4: subida (opcional, sin probar)
├── INSTALACION.md               # Cómo montar la plataforma desde cero
├── revisar_voz.py               # Transcribe una voz y mide dónde respira
├── serie_generar.py             # Series: genera los actos de un capítulo, con Veo o con Grok
├── serie_imagenes.py            # Grok: hojas de personaje e imágenes de partida editadas
├── imagen.py                    # Grok: una imagen suelta desde una descripción
└── serie_placas.py              # Series: correcciones, placas, portada y versión 9:16
```

### Las series

Además de los videos de artistas, el repo aloja **series cortas** que no usan voz
ni avatares: se generan a partir de fotografías de lugares reales. Comparten
`prompts/escenas/` y los scripts de serie, pero son independientes de las cuatro
fases.

| Serie | Motor | Documentación |
|---|---|---|
| *Algo pasa en Soatá* | Veo | **[serie_soata/README.md](serie_soata/README.md)** |
| La del celador, en Bogotá | Grok Imagine (xAI) | **[serie_celador/README.md](serie_celador/README.md)** |

Cada README tiene la historia, el arco, los costes, la forma de publicarla y las
lecciones de su motor. Aquí queda solo la mecánica de los scripts.

## Requisitos

**La instalación paso a paso, con versiones verificadas y comprobaciones, está en [INSTALACION.md](INSTALACION.md).** Aquí queda el resumen.

- **Ubuntu** (WSL2 en Windows) con GPU NVIDIA y CUDA. Probado en RTX 4060 de 8 GB.
- **FFmpeg** con `libfreetype` (para el texto en pantalla).
- **Cuatro entornos de Python separados**, porque sus dependencias son incompatibles entre sí:

| Entorno | Python | Para qué |
|---|---|---|
| `.venv` del proyecto | 3.12 | Orquestación, Gemini, yt-dlp |
| `~/omni_voice_project/venv` | 3.12 | OmniVoice + PyTorch 2.6 |
| `~/sadtalker_project/venv` | **3.11** | SadTalker + PyTorch 2.1.2 |
| `~/musetalk_project/venv` | **3.11** | MuseTalk + PyTorch 2.0.1 |

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

`revisar_voz.py` hace esa comprobación de una vez: transcribe el audio completo, lo corta por la mitad de cada silencio y transcribe cada trozo, de modo que se ve qué frase queda entre cada pausa y cuánto dura:

```bash
~/omni_voice_project/venv/bin/python revisar_voz.py output/DiomedesDiaz/voice.wav --desde 7
```

```
  [ 7.76- 9.61] Tus amistades, llegamos aquí...   <- pausa 0.68s
  [ 9.61-10.96] para compartir                    <- pausa 0.50s
```

No sirven las marcas de tiempo por palabra de Whisper: estiran el final de cada palabra sobre el silencio y dan 0,00 s donde en realidad hay medio segundo.

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

Felicitaciones con la voz de un personaje. Se salta la Fase 1: el texto se escribe a mano y **se enseña antes de generar nada**. Ejemplos terminados, con su `.json` de referencia: `output/DiomedesDiaz/saludos/wilmer-cortez.*` y `ticor.*`.

**1. Preparar.** Cambiar `active_character`, apartar a `_previo_<nombre>/` lo que haya en `output/<Personaje>/` si no está archivado, y escribir los dos archivos:

- `script.txt` — lo que se **oye**, en una sola línea.
- `script_meta.json` — `verses` con lo que se **ve** (un salto de línea por verso), `song` vacío para que no salga rótulo de canción, y más intentos de voz:

```json
{
  "song": "", "source": "saludo personalizado", "verbatim": false,
  "verses": "Hola, compadre Ticor,\nun saludo de cumpleaños\nde parte de tu amigo Diomedes.",
  "overrides": { "omnivoice": { "max_attempts": 8 } }
}
```

**2. La coletilla se deja.** Suena al final ("con mucho gusto" en Diomedes) y no sale escrita. Solo se anula si el texto ya acaba con ella, con `"characters": {"DiomedesDiaz": {"text_suffix": ""}}` dentro de `overrides`.

**3. Las pausas se escriben distinto en audio y en pantalla.** OmniVoice apenas se detiene con una coma: 0,08 s medidos. Donde haga falta que respire, `script.txt` lleva **puntos suspensivos** y `verses` conserva la puntuación normal. En el saludo de Wilmer Cortez, con comas la última parte salió de corrido; con suspensivos quedaron pausas de 0,24 a 0,68 s.

**4. Voz.** La Fase 2 comprueba sola el final, las palabras atropelladas, las pausas y que se dijo todo el texto, y repite hasta que sale bien:

```bash
.venv/bin/python 2_generate_voice.py
```

Si termina con *"AVISO: ninguna toma salió limpia"*, se queda con la mejor toma, pero **conviene no pasar al video**: se repite la voz o se revisa la puntuación. Los nombres poco comunes (Ticor, Cortez) conviene confirmarlos en la transcripción que guarda `voz_intentos.json`. `revisar_voz.py` sigue sirviendo para mirar las pausas a mano.

**5. Video.** `3_generate_video.py` y después `3c_lipsync.py`. Sin escena de Veo, salvo que se pida "completo".

**6. Archivar y restaurar.** Copiar `video_lipsync.mp4`, `voice.wav` y `script_meta.json` a `saludos/<destinatario>.mp4|.wav|.json`, añadiendo al `.json` un campo `audio` con el texto pronunciado y una `nota` con lo que hizo falta. Después, devolver `active_character` a su valor.

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

**2. Atropella palabras sueltas**, comprimiéndolas hasta hacerlas ininteligibles. Se detecta transcribiendo con Whisper y midiendo la duración de cada palabra: si alguna baja de `min_word_duration` (0.13 s), se regenera. Si el problema persiste en una frase concreta, bajar `omnivoice.speed` a 0.85-0.9 suele arreglarlo; es un ajuste típico de `overrides`.

**3. Dice la frase de corrido**, sin las pausas que marca el texto. Es lo que pasó en el primer saludo de Wilmer Cortez. Se detecta **cortando el audio por los silencios y transcribiendo cada trozo**, para saber con qué palabra termina cada frase de verdad. Una pausa pedida que no aparece como final de frase cuenta como defecto.

- Se exigen donde el texto de `script.txt` pone **puntos suspensivos** (`pausa_suspensivos`, 0,2 s) o **punto** (`pausa_punto`, 0,12 s), incluido el punto que la separa de la coletilla.
- **Las comas no se exigen.** OmniVoice apenas se detiene en ellas (0,08 s medidos), así que exigirlas haría rechazar casi todas las tomas. **Donde una pausa importe, se escriben suspensivos.**
- No sirven las marcas de tiempo por palabra de Whisper: estiran las palabras sobre el silencio y marcan 0 s donde hay medio segundo.

**4. Se salta o deforma palabras.** Se compara la transcripción con el texto. Si coinciden menos del 85 % de las palabras (`min_cobertura`), se regenera. En las tomas buenas sale 0,95-0,97; las diferencias normales son cosas como "pa" transcrito "para".

**Cómo decide.** Cada toma se diagnostica y, si sale limpia, se acepta. Si no, **adapta la siguiente** (desactivable con `adaptar: false`):

- Si atropella palabras, baja la velocidad 0,05, sin pasar de 0,8.
- Si falta la pausa de un punto, cambia ese punto por suspensivos. La exigencia sigue siendo la del punto: el cambio sirve para conseguir la pausa, no para pedir más.
- Si el final sale cortado, repite con la misma receta, porque ya hay coletilla.

Si se agotan los `max_attempts`, **se queda con la mejor toma, no con la última**, ponderando los defectos: corte y texto incompleto pesan 10, atropello 4 y cada pausa que falta 2. Cada ejecución deja `voz_intentos.json` junto a `voice.wav`, con el texto, la velocidad, los defectos, la transcripción y las frases con sus pausas de cada intento, y cuál se eligió.

Cada intento tarda unos 20-30 s entre la síntesis y el análisis.

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

**Coste y límites.** Cada clip son 8 segundos y cuesta unos **COP 1.500** (~$0.38) con el modelo Lite, medido sobre facturación real. Además del saldo hay un tope duro de cuota: el plan Tier 1 permite **10 generaciones de video al día** y 2 por minuto, y se renueva a medianoche del Pacífico —las 3 de la madrugada en Colombia—. Un 429 casi siempre es la cuota, no el saldo. Requiere **facturación activada** en el proyecto de Google Cloud: el plan gratuito da cuota cero para video e imagen. Lo más seguro es comprar saldo prepago **con la recarga automática desactivada**, que actúa como tope real de gasto — un presupuesto de Cloud solo avisa, no detiene nada.

Las escenas se cachean en `output/escenas/` con el prompt en un `.json` al lado: repetir un prompt no se vuelve a pagar, y un resultado bueno se puede reproducir.

**Dos costuras conocidas.** Veo entrega 720x1280 y hay que ampliar a 1080x1920, así que la escena se ve algo más blanda que el avatar. Y si el audio dura más que los 8 segundos del clip, se congela el último fotograma; el módulo avisa por consola cuántos segundos quedan congelados. Para textos largos conviene subir `corte_s` o generar dos escenas.

### Fase 3c — Sincronía labial con MuseTalk (`3c_lipsync.py`, opcional)

SadTalker genera el video entero; MuseTalk **rehace solo la región labial** a partir del audio, y lo hace mejor. Se aplica encima del render sin tocar la voz ni el encuadre.

```bash
.venv/bin/python 3c_lipsync.py     # despues de la fase 3
```

Sale a `video_lipsync.mp4` y deja intacto el `video.mp4` original.

**Necesita un cuarto entorno**, con Python 3.11 y torch 2.0.1+cu118. Su instalación tiene varias trampas encadenadas:

- `chumpy`, dependencia de `mmpose`, no compila con setuptools moderno. Se instala `mmpose` con `--no-deps` y se añaden a mano sus dependencias reales; `chumpy` es para modelos corporales SMPL y no hace falta.
- `xtcocotools` viene compilado contra numpy 2, y todo el stack espera numpy 1.23.5. Hay que compilarlo desde fuente **con `--no-deps`**: sin eso, pip vuelve a subir numpy a 2.x en cada intento y el error se repite en bucle.
- `pkg_resources` desapareció de setuptools moderno: hace falta `setuptools<81`, igual que en SadTalker.
- El argumento `--unet_config` apunta por defecto al modelo v1 **aunque se pida `--version v15`**. Hay que pasarle la ruta a mano.

**Sobre la calidad y el tiempo.** MuseTalk tarda unos 5 minutos por clip, casi independientemente de la calidad del render de entrada: la mayor parte es cargar el modelo de 3.4 GB y detectar la cara en cada fotograma, no la inferencia en sí. Las dos rutas posibles:

| Ruta | SadTalker | MuseTalk | Total |
|---|---|---|---|
| 256 sin enhancer | ~2 min | ~5 min | ~7 min |
| 512 + GFPGAN | ~10 min | ~5 min | ~15 min |

La segunda se ve mejor, así que la mejora de MuseTalk **se suma** a la del enhancer en vez de sustituirla.

### El video "completo"

La combinación de mayor calidad encadena todo lo anterior, en este orden:

```
Fase 1 → Fase 2 → Fase 3 → Fase 3c → Fase 3b
texto     voz      retrato   lipsync   escena + montaje
```

**El orden importa.** El lipsync va sobre el retrato **antes** de montar la escena: así MuseTalk trabaja sobre la cara completa, y no sobre un video donde el rostro solo aparece los primeros segundos.

**Ojo:** hoy la Fase 3b lee `video.mp4` y no `video_lipsync.mp4`, así que para que la escena lleve los labios de MuseTalk hay que copiar uno sobre el otro antes de lanzarla. Ver *Arquitectura*.

Unos 20 minutos por clip de 15-20 s, y unos COP 1.500 si la escena es nueva. MuseTalk **escala con la duración** del clip, no es un coste fijo: los turnos cortos salen bastante más baratos en tiempo.

### Escribir monólogos inspirados en las canciones

El modo libre acepta cualquier tema si se le cambia el prompt. Dos técnicas que mejoran mucho el resultado:

**Elegir las canciones de referencia por análisis, no al azar.** En lugar de pasarle seis letras cualesquiera, se puntúa el corpus por campo semántico —términos de caída (`olvid`, `dolor`, `herid`, `adios`) frente a los de recuperación (`levant`, `seguir`, `volver`, `aprend`)— y se usan las que puntúan alto en ambos. Con 146 canciones, la diferencia entre una referencia temática y una aleatoria se nota mucho.

**Pedir el registro correcto.** Es fácil obtener tres cosas distintas según cómo se pida:

| Si se pide | Sale |
|---|---|
| "consejo en su estilo" | máximas encadenadas con su vocabulario |
| "que hable desde lo vivido" | anécdota con una escena concreta |
| "reflexión estoica" | principio aplicado, con serenidad |

Conviene decir explícitamente lo que **no** se quiere: nada de refranes encadenados, nada de contar una anécdota, y prohibir los arranques que el modelo repite por defecto.

### Repartir el texto sin cambiar el audio

`verses` alimenta a la vez el texto en pantalla y —vía `to_speech()`— lo que se pronuncia. Cuando una frase larga se parte y deja palabras huérfanas, la solución no es bajar el tamaño de letra: es **cortar la frase por sus comas** en líneas separadas.

Como `to_speech()` solo añade una coma a las líneas que no acaban en puntuación, partir por una coma existente deja el audio **idéntico** y arregla el reparto en pantalla. Merece la pena verificarlo antes de renderizar:

```python
m1.to_speech(antes) == m1.to_speech(despues)
```

### Fase 4 — Subida a TikTok (`4_upload_tiktok.py`)

Automatiza el navegador con Playwright. **Sin probar y con `dry_run: true`.** El flujo recomendado es subir a mano: los selectores de TikTok cambian sin aviso y no compensa depurar un scraper mientras el formato aún se está afinando.

## Video generado con Veo (`serie_generar.py`, `serie_placas.py`)

Cómo se hace una serie por capítulos a partir de fotografías, **sin voz clonada, avatar ni texto extraído de letras**: `serie_generar.py` genera los actos con **Veo** y `serie_placas.py` los corrige y los monta, solo con FFmpeg.

Usa la clave de Gemini, la carpeta `prompts/escenas/` y —lo que más limita— la **misma cuota diaria de video** que la Fase 3b: Veo da 10 generaciones al día y 2 por minuto.

Con este motor se produjo *Algo pasa en Soatá*: su historia, su arco, su calendario y los casos concretos están en **[serie_soata/README.md](serie_soata/README.md)**. Para una serie con la API de xAI, ver [Serie con Grok Imagine](#serie-con-grok-imagine-serie_imagenespy-imagenpy).

### La ficha de un capítulo

Cada capítulo es un JSON en `prompts/escenas/`. **Solo cuatro campos llegan al modelo**: `arquitectura`, `luz_prompt` (opcional), `comun` y el `prompt` de cada acto. El resto —`nota`, `riesgo`, `revision`, `leccion`, `montaje`...— es documentación para quien la lea y no se envía nunca. `arquitectura` se copia en los tres actos, porque es lo que frena al modelo cuando tiende a inventarse edificios al encadenar.

### El ciclo de producción

**1. Revisar lo que se va a enviar, sin gastar cuota:**

```bash
.venv/bin/python serie_generar.py prompts/escenas/cap6_los-que-vuelven.json --ver-prompts
```

**2. Generar acto por acto**, revisando cada uno antes de gastar el siguiente:

```bash
.venv/bin/python serie_generar.py prompts/escenas/cap6_los-que-vuelven.json --solo-acto 1
```

Cada acto parte del último fotograma del anterior, así la escena continúa sin corte. Con `--entrada IMAGEN` un acto parte de otra imagen: para probarlo antes de tener los previos, o para empezar desde el final de otro capítulo. Un acto puede traer en la ficha su propia `arquitectura` y `comun` cuando cambia de encuadre. Al terminar, se unen en `output/escenas/<ficha>_24s.mp4`. Con `--solo-acto`, el clip que hubiera se aparta como `_previo`. Sin esa opción genera los tres seguidos.

Tiene dos frenos. **Se niega a lanzar una ficha con campos `PENDIENTE`**. Y **se para si el fotograma desde el que va a encadenar tiene un brillo menor de 28**, salvo que se use `--forzar`: a oscuras el modelo deja de ver la arquitectura y se la inventa. En el capítulo 6, un acto que acabó en negro hizo que el siguiente saliera con otra iglesia.

**3. Revisar contra la foto original el encuadre entero**, no solo el elemento protagonista. Hay que ampliar las figuras y los bordes y medir el brillo. Un capítulo pasó la revisión con la cúpula perfecta y había perdido todo el parque de la izquierda.

**4. Montar**, sin gastar cuota. El comando exacto de cada capítulo queda guardado en el campo `montaje` de su ficha:

```bash
.venv/bin/python serie_placas.py output/escenas/cap6_los-que-vuelven_24s.mp4 \
    --numero 6 --titulo "Los que vuelven" --vertical --desde 1.8 --recorte 1136:720:0:0
```

| Opción | Para qué |
|---|---|
| `--vertical` | Añade la versión 9:16, con el plano encajado sobre su propia imagen desenfocada |
| `--desde S` | Descarta el arranque: Veo entra disolviendo desde la foto de partida, que suele ser de día |
| `--hasta S` | Corta antes de un defecto del final |
| `--recorte W:H:X:Y` | Deja fuera lo que Veo se inventó en un borde |
| `--sin-barras` | Desactiva el recorte automático de barras negras |
| `--noche` / `--sombras` | Oscurece un clip de día / levanta una noche tan cerrada que el sitio no se reconoce |
| `--portada S` / `--portada-negra` | Elige el fotograma de fondo de la placa de entrada, o la deja en negro |
| `--cierre TEXTO` | Texto de la placa final, CONTINUARÁ por defecto; el último capítulo usa FIN |

Además hace dos cosas solo. **Recorta las barras negras** únicamente si siguen ahí en tres momentos distintos del clip, porque Veo a veces las tiene solo medio segundo al principio. Y **elige de portada el fotograma más iluminado a partir del segundo 4**, porque las redes usan el primer fotograma de miniatura y una placa negra deja el Reel invisible en el feed.

Los clips crudos van a `output/escenas/`, los capítulos terminados a `output/serie/` y las versiones descartadas o de prueba a `output/serie/pruebas/`. Una ficha puede llevar su propia carpeta en `salida`, como hace la serie del celador.

### Cómo se le habla a Veo

Lo que costó descubrir generando una temporada entera. Los casos y las medidas están en `serie_soata/README.md`.

- **Una acción, no un ambiente.** Las postales —niebla, amaneceres— no retienen.
- **Cantidades exactas y destinos por su aspecto.** "EXACTAMENTE DOS figuras", "la iglesia de piedra con el portón bajo el arco", nunca "el edificio de la izquierda".
- **Nadie toca a nadie.** El contacto entre figuras es lo que peor genera el modelo: cuerpos fusionados, torsos truncados.
- **Noche real con una fuente de luz propia**, no noche americana. El modelo necesita un motivo para oscurecer, como una luz en el cielo o que la luz salga de una puerta. La noche americana sobre nubes soleadas delata el truco.
- **Lo pequeño no puede cargar la acción.** Si el efecto ocurre en algo que ocupa el 2 % del cuadro, el modelo agranda o duplica ese elemento hasta que se vea.
- **El foco de la acción recompone el plano.** Si todos caminan hacia una puerta, el modelo la centra y sacrifica lo que haya a los lados. Hay que fijar el encuadre en el prompt.
- **Lo que se mueve entero parece un recorte.** Una cúpula subiendo de una pieza pareció "de Chespirito". Funciona que se transforme a la vista, con fragmentos y polvo.
- **Al ampliar a 16:9, Veo inventa por los bordes.** Se revisan y se recortan en el montaje, sin pedirlo en el prompt: ahí podría desaparecer de golpe a mitad del clip.

## Serie con Grok Imagine (`serie_imagenes.py`, `imagen.py`)

La segunda serie —la del celador, en Bogotá— se produce con la **API de xAI** en vez de con
Veo. El orquestador es el mismo `serie_generar.py`: **elige motor según el modelo que declare
la ficha**, Grok si empieza por `grok` y Veo si no. Lo que cambia son los campos de la ficha y
que aquí también se generan las imágenes.

La historia, el estado y todo lo aprendido están en
**[serie_celador/README.md](serie_celador/README.md)**. Aquí queda la mecánica.

**La clave va en `.env` como `XAI_API_KEY`**, junto a la de Gemini. Es saldo de prepago: en la
consola de xAI conviene dejar el *auto top-up* desactivado, para que el gasto no pueda pasar
de lo cargado.

### Qué cuesta

| Concepto | Precio |
|---|---|
| Video, 480p | **$0,08 por segundo**: $0,32 un clip de 4 s, $0,40 uno de 5 s |
| Imagen, `grok-imagine-image-2.0` a 1k | **$0,06** (calidad media); $0,04 en baja, $0,08 a 2k |
| Capítulo real, cinco actos y sus imágenes | **$2,50 a $4,70**; la media va en $3,80 |

Los precios de imagen salen de `GET /v1/image-generation-models`, que se consulta gratis y
devuelve la tarifa por modelo.

### Lo que la ficha le pide a xAI

| Campo | Qué hace |
|---|---|
| `modelo` | `grok-imagine-video-1.5` |
| `duracion_s` | 1 a 15 s, frente a los 8 fijos de Veo. Un acto puede traer el suyo |
| `formato`, `resolucion` | `9:16` nativo y `480p`, `720p` o `1080p` |
| `audio` | Grok genera el sonido del clip |
| `referencias` | imágenes que anclan personajes y objetos; admite comodines |
| `salida`, `prefijo` | carpeta y prefijo de los clips, para que dos series no se pisen |
| `foto` | imagen de partida del primer acto |
| `entrada` en un acto | ese acto arranca de su propia imagen en vez de encadenar |
| `personaje` y `referencias` en un acto | quién sale **en ese acto**; con `""` y `[]`, el protagonista no aparece |
| `imagenes_previas` | las imágenes editadas que hay que generar antes: origen, destino e instrucción |

`--ver-peticion` imprime el cuerpo que se enviaría, con las imágenes resumidas, sin gastar
nada.

### Las imágenes

```bash
# hoja de personaje: el retrato 1 desde texto, los demás editándolo
.venv/bin/python serie_imagenes.py prompts/personajes/celador.json --solo 1
.venv/bin/python serie_imagenes.py prompts/personajes/celador.json --desde 2

# imágenes de partida de un capítulo, las que declara en imagenes_previas
.venv/bin/python serie_imagenes.py prompts/escenas/cel4_la-balsa.json

# una imagen suelta, para probar ideas
.venv/bin/python imagen.py "la plaza de noche con niebla" --desde foto.jpg
```

`serie_imagenes.py` sirve para las dos cosas según la ficha que reciba, aparta lo anterior en
`_previos/` y avisa de lo que va a costar. `imagen.py` es para pruebas sueltas: añade una
coletilla que fuerza el aspecto fotográfico —se quita con `--tal-cual`— y guarda en
`output/imagenes/`.

**Por qué hacen falta.** Un video arranca exactamente en su imagen de partida, así que la
noche, la plaza vacía o el pedestal sin estatua se hacen **antes**, en la imagen, que cuesta
$0,06 frente a $0,40 del clip.

### Las hojas de referencia

Lo que mantiene a un personaje igual entre capítulos:

- **`serie_celador/personaje/`**: los seis retratos del celador, generados una vez.
- **`serie_celador/figura/`**: la estatua de bronce, montada **gratis** con fotogramas de
  clips ya aprobados.

Se adjuntan con `referencias` en la ficha, y también sirven para objetos: las dos fotos de la
Balsa Muisca evitaron que el modelo la repintara.

### Diferencias con Veo que afectan al código

- **Cada clip vuelve con el tamaño que le toca** según su imagen de partida —400×736 y 480×848
  en el mismo capítulo—, así que `une()` los escala al mayor antes de concatenar.
- **La API de imagen devuelve JPEG** aunque se pida otra cosa: el tipo se detecta por el
  contenido, no por la extensión.
- **No hay cuota diaria** como los 10 de Veo, pero sí errores `429` por saturación: se
  reintenta y ya.
- **El montaje para redes es otro**: `serie_placas.py --encima` escribe el título sobre la
  imagen, sin placas negras, y `--facebook` lo deja visible desde el primer fotograma, que es
  la miniatura del Reel.

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
| `omnivoice.pausa_suspensivos` | Pausa mínima donde el texto pone `...` (0.2 s) |
| `omnivoice.pausa_punto` | Pausa mínima donde el texto pone punto (0.12 s) |
| `omnivoice.min_cobertura` | Parte del texto que debe reconocerse en la voz (0.85) |
| `omnivoice.adaptar` | Cambia velocidad y puntuación entre intentos (`true`) |
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
| llegamos aquí, pa' compartir, esa... | de corrido, sin pausas | suspensivos en `script.txt`, comas en `verses` |
| pa' | con el apóstrofo, leído raro | `pa` sin apóstrofo en `script.txt` |
| Wiliam | "William", a la inglesa | escribirlo fonéticamente |
| Ticor | "Ticór", aguda | `Tícor` con tilde en `script.txt`; en pantalla, sin ella |

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
