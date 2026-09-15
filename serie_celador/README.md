# La serie del celador

*Nombre provisional.* Segunda serie corta del proyecto, con **protagonista fijo**, pensada
para TikTok y producida con **Grok Imagine** en vez de Veo.

La primera serie, *Algo pasa en Soatá*, está en [serie/README.md](../serie/README.md). Casi
todo lo aprendido allí se aplica aquí, y está resumido más abajo.

## Estado

| | |
|---|---|
| Protagonista | decidido: un celador de ronda nocturna. Ficha en [prompts/personajes/celador.json](../prompts/personajes/celador.json) |
| Hoja de personaje | **pendiente de generar** en Grok Imagine: seis retratos ya escritos |
| Locación | **Bogotá**, empezando en la Plaza de Bolívar |
| Historia | hay una propuesta, **sin aprobar**: el guion todavía se está pensando |
| Producción | orquestada desde el proyecto con la API de xAI, igual que la serie anterior con Veo |
| Clave | falta `XAI_API_KEY` en el `.env` |
| Capítulos | ninguno |

## Qué es

Lo que se repite de la primera serie no es la trama, sino la fórmula: **un sitio real donde
ocurre algo que no debería**, contado sin diálogo y sin explicar nada. Lo nuevo es que
alguien lo presencia siempre: el celador.

## El protagonista

Un celador de ronda nocturna, de unos 55 años, con gorra, chaqueta azul marino con bandas
reflectantes y una linterna grande. La descripción completa, las reglas para filmarlo y los
seis retratos de la hoja de personaje están en su ficha.

**Por qué un celador**, y no cualquier protagonista:

- Tiene **motivo para estar solo de noche**, que es cuando pasa todo.
- **La linterna es la fuente de luz.** Sin una luz propia dentro de la escena, el modelo
  devuelve el plano de día o pierde la arquitectura. Es lo que resolvió el portón iluminado
  del capítulo 6 y los motores del 7.
- **Su haz decide lo que se ve.** Que solo veamos lo que él alumbra es, además de barato, la
  firma visual de la serie.

## Cómo se produce

**Igual que la serie anterior, con el mismo comando.** `serie_generar.py` decide el motor
según el modelo que declare la ficha: si empieza por `grok` usa la API de xAI, y si no, Veo.
Lo demás no cambia — encadenado por el último fotograma, guardián de brillo, `--solo-acto`,
`--entrada` y el montaje con `serie_placas.py`.

```bash
.venv/bin/python serie_generar.py prompts/escenas/cel1_la-plaza-quieta.json --ver-peticion
.venv/bin/python serie_generar.py prompts/escenas/cel1_la-plaza-quieta.json --solo-acto 1
```

**Lo que la ficha puede pedirle a xAI**, con los nombres que usa su API:

| Campo de la ficha | Qué hace |
|---|---|
| `modelo` | `grok-imagine-video-1.5` |
| `duracion_s` | 1 a 15 segundos, frente a los 8 fijos de Veo |
| `formato` | `9:16` nativo, que es lo que pide TikTok |
| `resolucion` | `480p`, `720p` o `1080p` |
| `audio` | genera sonido, activado por defecto |
| `referencias` | imágenes que anclan al personaje; admite comodines para tomar la hoja entera |
| `foto` | fotograma de partida, opcional |

`--ver-peticion` muestra el cuerpo que se enviaría, con las imágenes resumidas, sin gastar
nada.

**Cómo funciona por dentro.** `POST /v1/videos/generations` devuelve un `request_id` y se
sondea `GET /v1/videos/{id}` hasta que el estado es `done`; entonces se descarga el video.

**Sin foto de partida.** La API también hace texto a video, y eso cambia las cosas en Bogotá:
la Plaza de Bolívar, la Catedral o Monserrate los conoce el modelo, así que no hace falta
fotografiarlos. En Soatá era imprescindible, porque nadie conoce esa plaza. Queda por
comprobar si los reconoce bien: es lo primero que hay que probar.

**Continuidad del personaje.** Según Grok, su *Reference-to-Video* admite hasta siete
imágenes de referencia por generación y con ellas ancla cara, cuerpo y ropa. De ahí la hoja
de personaje: se generan los retratos **una sola vez** y se adjuntan **en todos los
capítulos**, empezando el prompt por "el celador de las imágenes de referencia, la misma
cara, la misma gorra...". Dentro de un capítulo, los actos siguen encadenándose por el
último fotograma del anterior, igual que en Soatá.

## Costes

**Estimación de Grok** para la fase inicial, no medida por nosotros:

| Concepto | Cantidad | Unitario | Subtotal |
|---|---|---|---|
| Imágenes del personaje principal | 12-18 | $0,02-0,06 | $0,30-1,00 |
| Variaciones de expresión, ángulo y ropa | 8-12 | $0,02-0,06 | $0,20-0,70 |
| Posible personaje secundario | 6-10 | $0,02-0,06 | $0,15-0,50 |
| **Total** | | | **$0,70-2,20** |

Recomienda usar el modelo de calidad media-alta para que las caras salgan consistentes.

**El video, según la documentación de xAI:** **$0,080 por segundo** en la tarifa base.
OpenRouter publica una horquilla de $0,08 a 480p hasta $0,25 a 1080p; para 720p no hay dato
público. Un clip de 8 s sale entre **$0,64 y $2,00**.

**Comparado con Veo**, que es lo que sí medimos: allí un clip de 8 s costó **COP 1.500**
(~$0,38), con 3,3 generaciones por capítulo. Grok es **de 2 a 5 veces más caro por segundo**.
A cambio da vertical nativo, duración de hasta 15 s, imágenes de referencia para el personaje
y no tiene el tope de 10 generaciones al día.

Una temporada de cinco capítulos de dos clips rondaría los **$10 a 480p**.

## Formato, pensado para TikTok

- **Vertical nativo.** Si la imagen de partida es vertical, el video sale vertical. Lo
  apaisado metido en 9:16 con bandas borrosas se nota.
- **15-20 segundos**, no 27.
- **Sin placa de título al principio**: se lleva 2,5 s de los primeros segundos, que son los
  que deciden. El título va escrito sobre la primera imagen.
- **Que cierre en bucle**: si el último fotograma se parece al primero, el video se repite sin
  costura.
- El gancho **no puede ser reconocer el sitio**: TikTok reparte por interés, no por
  geografía. Tiene que entenderse en dos segundos sin saber dónde es.

## Reglas heredadas de Soatá

Las que costaron caro y siguen valiendo:

- **Una acción con principio y final**, no un ambiente.
- **Cantidades exactas** y destinos descritos por su aspecto, nunca por su posición.
- **Nadie toca a nadie**: el contacto entre figuras es lo que peor genera el modelo.
- **Noche con una fuente de luz dentro de la escena**, nunca oscurecida después.
- **Lo pequeño no puede cargar la acción**: si el efecto pasa en algo que ocupa el 2 % del
  cuadro, el modelo lo agranda o lo duplica.
- **Revisar cada clip contra la foto original**, el encuadre entero y no solo el elemento
  protagonista, ampliando figuras y bordes.

## La historia

**Propuesta sin aprobar.** El guion se sigue pensando, así que esto queda anotado como punto
de partida, no como decisión.

Un celador de ronda encuentra algo en la Plaza de Bolívar y lo va siguiendo por la ciudad:

1. **La plaza quieta.** Tres de la madrugada. Cruza alumbrando y todas las palomas están
   despiertas e inmóviles, mirando al mismo punto. Sigue con la linterna lo que miran: las
   puertas de la Catedral, entreabiertas.
2. **La marca.** En el suelo hay una figura trazada entre las piedras, húmeda, recién hecha.
   Levanta la linterna y la misma figura está en la puerta.
3. **El rastro.** La Candelaria. La marca aparece en una puerta, luego en otra más arriba.
   Siempre subiendo hacia el cerro.
4. **Lo que señala.** Desde una esquina en alto se ve Monserrate, y las luces del santuario se
   apagan en el mismo orden que tenía la marca.
5. **El relevo.** Vuelve a la plaza al amanecer. No hay marcas y las palomas están normales.
   Llega su relevo y, cosida en la chaqueta, lleva la figura.

El remate repite el hallazgo de Soatá —**alguien ya lo sabía**— pero ahora con alguien a
quien le pasa.

## Pendiente

1. **Cerrar el guion.** Es lo único que bloquea todo lo demás.
2. **`XAI_API_KEY` en el `.env`**; la línea ya está en `.env.example`.
3. **Generar la hoja de personaje**, unos $0,30. La API también hace imágenes, así que puede
   hacerse desde aquí.
4. **Un clip de prueba a 480p**, unos $0,80, para ver dos cosas: si reconoce la Plaza de
   Bolívar sin foto, y si mantiene al mismo celador con las imágenes de referencia.
