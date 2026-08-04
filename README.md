# Auto TikTok Pipeline

Pipeline automatizado de código abierto para la generación y publicación de contenido vertical (para TikTok y Reels) utilizando **Gemini API** para la ideación de guiones, **OmniVoice** para la clonación local de voz con soporte multi-personaje, y automatización web.

## Estructura del Proyecto


auto_tiktok_pipeline/
├── assets/
│   ├── personaje_1/
│   │   ├── ref_audio.wav
│   │   ├── ref_text.txt
│   │   └── avatar.png
│   └── personaje_2/
│       ├── ref_audio.wav
│       ├── ref_text.txt
│       └── avatar.png
├── config.json              # Configuración general y selección de personaje activo
├── main.py                  # Script orquestador principal
├── 1_generate_text.py       # Módulo 1: Generación de frase con Gemini API
├── 2_generate_voice.py      # Módulo 2: Creación de WAV con OmniVoice
├── 3_generate_video.py      # Módulo 3: Creación de video vertical (Avatar + Sincronización)
└── 4_upload_tiktok.py       # Módulo 4: Carga automática a TikTok


## Fases y Detalles Técnicos de los Módulos

El flujo de trabajo se ejecuta de forma secuencial a través de los siguientes componentes, herramientas y librerías:

### Fase 1: Generación del Guion
* Módulo: `1_generate_text.py`
* Herramienta / API: Google GenAI SDK (`google-genai`).
* Descripción: Invocación de la API de Gemini mediante un prompt estructurado para redactar de forma dinámica la frase o guion que interpretará el personaje activo.

### Fase 2: Síntesis y Clonación de Voz
* Módulo: `2_generate_voice.py`
* Herramienta / Librería: OmniVoice (`omnivoice.cli.infer`) ejecutándose en un entorno virtual con PyTorch (Soporte CUDA para GPU RTX 4060).
* Descripción: Lectura de los parámetros del personaje activo desde `config.json` para procesar el texto obtenido en la Fase 1, empleando el archivo `.wav` y el texto de referencia correspondientes.

### Fase 3: Composición de Video Vertical
* Módulo: `3_generate_video.py`
* Herramienta / Librería: SadTalker / Wav2Lip y FFmpeg (`ffmpeg-python`).
* Descripción: Sincronización del movimiento facial del avatar a partir de la imagen y el audio generado, re-escalando y empaquetando el resultado final en un contenedor MP4 con resolución vertical (9:16 / 1080x1920).

### Fase 4: Automatización de Publicación
* Módulo: `4_upload_tiktok.py`
* Herramienta / Librería: Playwright o Selenium (Python).
* Descripción: Automatización de un navegador web en entorno headless o visible para la carga desatendida del video resultante en la plataforma TikTok.

## Requisitos Previos

* Sistema operativo: **Ubuntu** (vía WSL2 recomendado en Windows) con controladores de GPU configurados.
* Hardware: Tarjeta gráfica NVIDIA (probado en RTX 4060 con soporte CUDA).
* Entorno virtual de Python configurado con PyTorch compatible con CUDA.
* Librería **OmniVoice** instalada (`k2-fsa/OmniVoice`).

## Configuración (`config.json`)

El archivo centraliza la gestión multi-personaje y las rutas de los recursos multimedia:

{
  "active_character": "personaje_1",
  "characters": {
    "personaje_1": {
      "name": "Carlos Tech",
      "audio_path": "assets/personaje_1/ref_audio.wav",
      "audio_text": "Texto exacto que se dice en el audio de referencia.",
      "image_path": "assets/personaje_1/avatar.png"
    }
  }
}

## Uso del Orquestador (`main.py`)

Para ejecutar todas las fases del pipeline de forma automatizada:

python3 main.py
