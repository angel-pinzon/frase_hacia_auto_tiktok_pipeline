# Instalación

Guía para montar la plataforma desde cero: el proyecto, los tres motores locales (OmniVoice, SadTalker y MuseTalk) y los servicios de Google.

**Todas las versiones de esta guía están verificadas** en la máquina donde corre hoy el proyecto, en septiembre de 2026. Los proyectos de terceros evolucionan y sus propias guías pueden recomendar versiones más nuevas; estas son las que se sabe que funcionan juntas.

Para entender cómo encajan las piezas, ver la sección *Arquitectura* del [README](README.md).

## Antes de empezar

### Qué hace falta

| | Verificado con |
|---|---|
| Sistema | Windows con **WSL2** y **Ubuntu 24.04** |
| GPU | NVIDIA con **8 GB de VRAM o más**; probado en RTX 4060 Laptop |
| Controlador | El controlador NVIDIA **de Windows** con soporte WSL (591.66). Dentro de Ubuntu **no se instala ningún controlador NVIDIA**: la GPU llega desde Windows, y cada PyTorch trae su propio runtime de CUDA |
| Disco | **~30 GB**: cada entorno de motor ocupa 5-6 GB, más 10 GB de modelos |
| Tiempo | Un par de horas, casi todo descargas |

### Lo que no viene en el repositorio

El `.gitignore` excluye el material con derechos de autor y los secretos. Un clon del repositorio llega **sin**:

- **Letras** (`lyrics/<Personaje>/*.txt`): 146 de Diomedes, 76 de Yeison y 755 de Vicente.
- **Audios de referencia y avatares** (`assets/<Personaje>/`).
- **Fotos de las locaciones de la serie** (`assets/*.jpg`).
- **La clave de Gemini** (`.env`).

Hay que copiarlos desde una copia de seguridad. **Las fotos y los audios no se pueden regenerar**: si se pierden, se pierden. El README explica cómo conseguir material nuevo si hiciera falta.

### Estructura de carpetas que se va a crear

```
~/frase_hacia_auto_tiktok_pipeline/   # este repositorio, con su .venv
~/omni_voice_project/                 # OmniVoice/ y venv/
~/sadtalker_project/                  # SadTalker/ y venv/
~/musetalk_project/                   # MuseTalk/ y venv/
```

Los motores van **fuera** del repositorio y cada uno con su propio entorno de Python, porque sus dependencias son incompatibles entre sí. Se pueden poner en otro sitio, pero entonces hay que ajustar las rutas en el paso 6.

## 1. Sistema

```bash
sudo apt update
sudo apt install -y git ffmpeg fonts-dejavu-core build-essential \
    python3.12 python3.12-venv python3.12-dev

# Python 3.11, que necesitan SadTalker y MuseTalk (Ubuntu 24.04 trae 3.12)
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

- `build-essential` y `python3.11-dev` hacen falta porque MuseTalk tiene que **compilar `xtcocotools` desde el código fuente** (paso 5).
- `fonts-dejavu-core` aporta la fuente del texto en pantalla.

**Comprobar:**

```bash
nvidia-smi                                   # debe listar la GPU
ffmpeg -version | grep -o enable-libfreetype # debe imprimir la cadena
ls /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
python3.11 --version && python3.12 --version
```

Si `nvidia-smi` no encuentra la GPU, el problema está en el controlador de Windows o en la versión de WSL, no en Ubuntu.

## 2. El proyecto

```bash
cd ~
git clone https://github.com/angel-pinzon/frase_hacia_auto_tiktok_pipeline.git
cd frase_hacia_auto_tiktok_pipeline

python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt yt-dlp
```

`yt-dlp` no está en `requirements.txt`: solo se usa para extraer audios de referencia de YouTube.

Después, copiar el material que no viene en el repositorio: `lyrics/`, el contenido de `assets/` y el `.env` (paso 7).

## 3. OmniVoice — voz clonada

Python **3.12** con **PyTorch 2.6.0 + CUDA 12.4**. Verificado con el commit `28bc088` de OmniVoice.

```bash
mkdir -p ~/omni_voice_project && cd ~/omni_voice_project
git clone https://github.com/k2-fsa/OmniVoice.git

python3.12 -m venv venv
venv/bin/pip install torch==2.6.0 torchaudio==2.6.0 \
    --index-url https://download.pytorch.org/whl/cu124
venv/bin/pip install -e OmniVoice
```

Se instala en **modo editable** (`-e`), que es como el proyecto lo invoca: `python -m omnivoice.cli.infer`.

**Los modelos se descargan solos la primera vez que se usa**, en `~/.cache/huggingface/`: `k2-fsa/OmniVoice` (3,1 GB) y `openai/whisper-large-v3-turbo` (1,6 GB). Whisper vive en este entorno porque la Fase 2 lo usa para detectar palabras atropelladas, y también lo usa `revisar_voz.py`.

La guía de OmniVoice recomienda hoy PyTorch 2.8 con CUDA 12.8. No se ha probado aquí; la combinación 2.6.0 + cu124 es la que funciona con el resto del proyecto.

**Comprobar:**

```bash
cd ~/omni_voice_project/OmniVoice
../venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
../venv/bin/python -m omnivoice.cli.infer --help
```

## 4. SadTalker — retrato animado

Python **3.11** con **PyTorch 2.1.2 + torchvision 0.16.2 + CUDA 12.1**. Verificado con el commit `cd4c046` de SadTalker.

```bash
mkdir -p ~/sadtalker_project && cd ~/sadtalker_project
git clone https://github.com/OpenTalker/SadTalker.git

python3.11 -m venv venv
venv/bin/pip install torch==2.1.2 torchvision==0.16.2 \
    --index-url https://download.pytorch.org/whl/cu121
venv/bin/pip install -r SadTalker/requirements.txt
venv/bin/pip install "setuptools<81" -U imageio imageio-ffmpeg

cd SadTalker && bash scripts/download_models.sh
```

Cada línea resuelve un problema concreto:

- **Python 3.11 y no 3.12**: `numpy==1.23.4` no tiene paquete precompilado para 3.12 e intenta compilarse desde el código fuente, sin éxito.
- **torch 2.1.2 y torchvision 0.16.2**: `basicsr` importa un módulo que desapareció en torchvision 0.17.
- **`setuptools<81`**: `librosa` necesita `pkg_resources`, que ya no está en las versiones nuevas.
- **Actualizar `imageio`**: la versión que fija SadTalker entra en recursión infinita al escribir el video.

`download_models.sh` baja **unos 2,4 GB**: 1,7 GB en `checkpoints/` (los modelos de 256 y 512 px) y 700 MB en `gfpgan/weights/` (GFPGAN y los detectores de cara, RetinaFace incluido).

**Comprobar:**

```bash
cd ~/sadtalker_project/SadTalker
../venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
../venv/bin/python inference.py --help
ls checkpoints/SadTalker_V0.0.2_512.safetensors gfpgan/weights/GFPGANv1.4.pth
```

## 5. MuseTalk — sincronía labial

Python **3.11** con **PyTorch 2.0.1 + CUDA 11.8** y la pila de OpenMMLab. Verificado con el commit `0a89dec` de MuseTalk.

Es la instalación más delicada. **Estos comandos se han reconstruido** a partir de la guía oficial de MuseTalk, de las versiones que hay instaladas y de los problemas que aparecieron; no son un registro literal de lo que se ejecutó. Las versiones sí están comprobadas.

```bash
mkdir -p ~/musetalk_project && cd ~/musetalk_project
git clone https://github.com/TMElyralab/MuseTalk.git

python3.11 -m venv venv
venv/bin/pip install torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 \
    --index-url https://download.pytorch.org/whl/cu118
venv/bin/pip install -r MuseTalk/requirements.txt
venv/bin/pip install "setuptools<81" "numpy==1.23.5" cython openmim \
    "huggingface_hub[cli]" gdown

# Pila de OpenMMLab
venv/bin/mim install mmengine
venv/bin/mim install "mmcv==2.0.1"
venv/bin/mim install "mmdet==3.1.0"

# mmpose sin sus dependencias, porque arrastra chumpy
venv/bin/pip install "mmpose==1.1.0" --no-deps
venv/bin/pip install json_tricks munkres matplotlib scipy

# xtcocotools compilado aqui, contra numpy 1.23.5
venv/bin/pip install "xtcocotools==1.14.3" --no-deps --no-build-isolation --no-binary xtcocotools

cd MuseTalk && sh ./download_weights.sh
```

Lo que evita cada paso especial:

- **`mmpose` con `--no-deps`**: una de sus dependencias, `chumpy`, no compila con un setuptools moderno. `chumpy` sirve para modelos corporales SMPL y MuseTalk no la usa, así que se instala `mmpose` sin dependencias y se añaden a mano las que sí hacen falta.
- **`xtcocotools` compilado aquí**: el paquete precompilado viene hecho contra numpy 2, y toda la pila espera numpy 1.23.5. **Las tres opciones son necesarias.** Sin `--no-deps`, pip vuelve a subir numpy a 2.x y el error se repite en bucle. `--no-build-isolation` compila contra el numpy del entorno, y por eso hace falta `cython` instalado antes.
- **`setuptools<81`**, por `pkg_resources`, igual que en SadTalker.

`download_weights.sh` deja **unos 4 GB** en `models/`: `musetalkV15/` (3,2 GB), `dwpose/`, `sd-vae/`, `whisper/` y `face-parse-bisent/`. Las carpetas `musetalk/` y `syncnet/` pueden quedar vacías: son del modelo v1 y del entrenamiento, que no se usan.

**FFmpeg:** la guía oficial pide un FFmpeg estático aparte. **No hace falta**: MuseTalk lo añade al `PATH` si existe, pero si no existe usa el del sistema, que ya está instalado desde el paso 1.

**Comprobar:**

```bash
cd ~/musetalk_project/MuseTalk
../venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
../venv/bin/python -c "import mmcv, mmdet, mmpose, xtcocotools; print(mmcv.__version__, mmdet.__version__, mmpose.__version__)"
ls models/musetalkV15/unet.pth models/musetalkV15/musetalk.json
```

Debe imprimir `2.0.1 3.1.0 1.1.0`.

## 6. Ajustar `config.json`

`config.json` apunta a los motores con **rutas absolutas**, y las que vienen en el repositorio son las de la máquina original (`/home/sixto/...`). Son seis:

| Clave | Apunta a |
|---|---|
| `omnivoice.python` | `~/omni_voice_project/venv/bin/python` |
| `omnivoice.cwd` | `~/omni_voice_project/OmniVoice` |
| `video.python` | `~/sadtalker_project/venv/bin/python` |
| `video.sadtalker_dir` | `~/sadtalker_project/SadTalker` |
| `lipsync.python` | `~/musetalk_project/venv/bin/python` |
| `lipsync.musetalk_dir` | `~/musetalk_project/MuseTalk` |

Si se ha seguido la estructura de esta guía con otro usuario, basta con cambiar el directorio personal:

```bash
cd ~/frase_hacia_auto_tiktok_pipeline
sed -i "s|/home/sixto|$HOME|g" config.json
grep -n '"/home' config.json    # deben aparecer tus rutas
```

No hay que tocar `lipsync.unet_config` ni `lipsync.unet_model_path`. Parecen redundantes, pero MuseTalk carga por defecto la configuración del modelo v1 **aunque se le pida la v1.5**, y esas dos claves lo corrigen.

## 7. Servicios de Google

### Gemini (texto)

1. Crear una clave en **Google AI Studio**.
2. Guardarla en `.env`, en la raíz del proyecto:

```bash
echo 'GEMINI_API_KEY=tu_clave' > ~/frase_hacia_auto_tiktok_pipeline/.env
```

El `.env` está en el `.gitignore` y no debe subirse nunca. `.env.example` es la plantilla vacía.

### Veo (video)

Veo lo usan la Fase 3b y la serie. **El plan gratuito tiene cuota cero para video**, así que hay que activar la facturación en el proyecto de Google Cloud asociado a la clave.

- Lo más seguro es **saldo prepago con la recarga automática desactivada**. Funciona como tope real de gasto; un presupuesto de Cloud solo avisa, no detiene nada.
- Con el plan **Tier 1** hay **10 generaciones de video al día** y 2 por minuto. La cuota se renueva a medianoche del Pacífico, las 3 de la madrugada en Colombia.
- Cada clip de 8 segundos cuesta unos **COP 1.500** con el modelo `veo-3.1-lite-generate-preview`.

Sin facturación, todo lo demás funciona: solo fallan la Fase 3b y la serie.

## 8. Comprobar la instalación completa

De más barato a más caro:

**1. Los tres entornos ven la GPU** (gratis, segundos):

```bash
for v in omni_voice sadtalker musetalk; do
  echo -n "$v: "; ~/${v}_project/venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
done
```

Las tres líneas deben acabar en `True`.

**2. Gemini responde** (céntimos):

```bash
cd ~/frase_hacia_auto_tiktok_pipeline
.venv/bin/python 1_generate_text.py
```

Debe escribir `output/<personaje activo>/script.txt`. Si falla con 404, el modelo de `gemini.model` no está disponible para esa clave.

**3. Voz** (gratis, menos de un minuto; la primera vez descarga 4,7 GB de modelos):

```bash
.venv/bin/python 2_generate_voice.py
~/omni_voice_project/venv/bin/python revisar_voz.py output/YeisonJimenez/voice.wav
```

**4. Video rápido** (gratis, ~2 minutos). Para comprobar SadTalker sin esperar los 10 minutos de la calidad alta, bajar temporalmente la calidad en `script_meta.json`:

```json
"overrides": { "video": { "size": 256, "enhancer": "" } }
```

```bash
.venv/bin/python 3_generate_video.py
```

Si la cara no se encuentra o el encuadre sale con barras negras, revisar que existe `gfpgan/weights/detection_Resnet50_Final.pth`.

**Después de la prueba, quitar ese `overrides`**, o los siguientes videos de ese personaje saldrán en baja calidad.

**5. Labios** (gratis, ~5 minutos):

```bash
.venv/bin/python 3c_lipsync.py
```

Debe dejar `output/<personaje>/video_lipsync.mp4`.

**6. Veo** (una generación de las 10 diarias, ~COP 1.500). Solo si se va a usar:

```bash
.venv/bin/python serie_generar.py prompts/escenas/cap6_los-que-vuelven.json --ver-prompts   # gratis
.venv/bin/python 3b_add_scenes.py                                                         # gasta cuota
```

## Opcional

**Fase 4, subida automática a TikTok.** Está sin probar y el flujo recomendado es subir a mano. Para instalarla:

```bash
.venv/bin/pip install playwright
.venv/bin/playwright install --with-deps chromium
```

## Problemas conocidos

| Síntoma | Causa | Arreglo |
|---|---|---|
| `nvidia-smi` no ve la GPU | Controlador de Windows sin soporte WSL | Actualizar el controlador en Windows; no instalar uno dentro de Ubuntu |
| numpy intenta compilarse al instalar SadTalker | Entorno con Python 3.12 | Rehacer el entorno con `python3.11` |
| `No module named 'torchvision.transforms.functional_tensor'` | torchvision 0.17 o más nuevo | torch 2.1.2 + torchvision 0.16.2 |
| `No module named 'pkg_resources'` | setuptools 81 o más nuevo | `pip install "setuptools<81"` |
| SadTalker se cuelga al escribir el video | `imageio` 2.19.3 | `pip install -U imageio imageio-ffmpeg` |
| `chumpy` falla al compilar | Dependencia de mmpose | `mmpose` con `--no-deps` |
| Error de ABI de numpy con `xtcocotools`, que vuelve tras cada intento | Paquete compilado contra numpy 2 y pip subiendo numpy | Compilarlo con `--no-deps --no-build-isolation --no-binary` |
| MuseTalk carga pesos que no cuadran | Configuración v1 por defecto | Mantener `lipsync.unet_config` y `unet_model_path` |
| Error críptico de OpenCV en SadTalker | Avatar demasiado grande | Lo evita `video.max_source`; no quitarlo |
| `FileNotFoundError` al lanzar un motor | Rutas de `config.json` de otra máquina | Paso 6 |
| 429 al generar con Veo | Cuota diaria agotada, casi nunca falta de saldo | Esperar a las 3 de la madrugada |

Más detalle de cada uno en el [README](README.md), en *Requisitos* y en las secciones de cada fase.
