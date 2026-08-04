# Auto TikTok Pipeline

Pipeline automatizado de código abierto para la generación y publicación de contenido vertical (para TikTok y Reels) utilizando **Gemini API** para la ideación de guiones, **OmniVoice** para la clonación local de voz con soporte multi-personaje, y automatización web.

## Estructura del Proyecto

```text
auto_tiktok_pipeline/
│
├── assets/
│   ├── personaje_1/
│   │   ├── ref_audio.wav
│   │   ├── ref_text.txt
│   │   └── avatar.png
│   └── personaje_2/
│       ├── ref_audio.wav
│       ├── ref_text.txt
│       └── avatar.png
│
├── config.json              # Configuración general y selección de personaje activo
├── main.py                  # Script orquestador principal
├── 1_generate_text.py       # Módulo 1: Generación de frase con Gemini API
├── 2_generate_voice.py      # Módulo 2: Creación de WAV con OmniVoice
├── 3_generate_video.py      # Módulo 3: Creación de video vertical (Avatar + Sincronización)
└── 4_upload_tiktok.py       # Módulo 4: Carga automática a TikTok# frase_hacia_auto_tiktok_pipeline
