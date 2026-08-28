# Guiones

Diálogos entre personajes, generados con el modo libre de la Fase 1.

- El `.json` es la fuente: lleva los turnos con quién habla en cada uno, y es
  lo que consume la producción.
- El `.txt` es solo legible, y **se regenera desde el `.json`**. No editarlo:
  los cambios se harían sobre el JSON.

Todo el texto es **original**, escrito por el modelo imitando la forma de hablar
de cada artista. Antes de guardarse se verifica que **ninguna línea sea textual**
de sus letras, con `is_verbatim()` de la Fase 1. Por eso estos archivos sí se
versionan: no contienen material con derechos.

Ninguno atribuye una canción concreta: son recreaciones, no citas.
