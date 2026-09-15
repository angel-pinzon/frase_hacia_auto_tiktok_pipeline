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
| Locación | **sin decidir**: Bogotá o Soatá |
| Historia | sin escribir |
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

**El reparto del trabajo.** Grok Imagine no se puede llamar desde el pipeline, así que:

1. Aquí se escriben los prompts y la ficha del capítulo.
2. Tú generas los clips en Grok Imagine y los dejas en `output/escenas/`.
3. Aquí se revisan los fotogramas, se corrigen y se montan con `serie_placas.py`.

El montaje es independiente del modelo: las barras, los recortes, la luz, la portada, las
placas y el vertical funcionan igual con un mp4 venga de donde venga.

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

**Referencia de lo que costó la otra serie**, esto sí medido: cada clip de 8 s con Veo salió
por unos **COP 1.500** (~$0,38), con **3,3 generaciones por capítulo** y un tope de 10 al día.
Falta saber qué cuesta un video en Grok para poder comparar de verdad.

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

## Pendiente

1. **Decidir la locación**: Bogotá o Soatá.
2. **Generar la hoja de personaje** con los seis retratos.
3. **Un capítulo de prueba** con el mismo prompt en Grok y en Veo, para comparar cuál conserva
   mejor la arquitectura y rompe menos las figuras.
4. Escribir la historia y el arco.
