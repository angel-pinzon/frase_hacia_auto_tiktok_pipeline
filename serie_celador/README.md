# La serie del celador

*Nombre provisional.* Segunda serie corta del proyecto, con **protagonista fijo**, pensada
para TikTok y producida con **Grok Imagine** en vez de Veo.

La primera serie, *Algo pasa en Soatá*, está en [serie_soata/README.md](../serie_soata/README.md). Casi
todo lo aprendido allí se aplica aquí, y está resumido más abajo.

## Estado

| | |
|---|---|
| Protagonista | decidido: un celador de ronda nocturna. Ficha en [prompts/personajes/celador.json](../prompts/personajes/celador.json) |
| Hoja de personaje | **dos**: el celador, seis retratos en `serie_celador/personaje/`, hechos con `serie_imagenes.py`; y la figura de bronce, cuatro fotogramas de clips aprobados en `serie_celador/figura/` |
| Locación | **Bogotá**, empezando en la Plaza de Bolívar. Foto en `assets/plazaBolivar1.jpg` y su recorte vertical |
| Historia | **temporada de 7 capítulos decidida**: el 1 y el 2 son del usuario, del 3 al 7 los propuso Claude y el usuario los aprobó |
| Producción | orquestada desde el proyecto con la API de xAI, igual que la serie anterior con Veo |
| Clave | `XAI_API_KEY` en el `.env`, comprobada |
| Capítulos | **del 1 al 4 terminados**, con su versión de TikTok y de Facebook en `serie_celador/output/` y `serie_celador/facebook/`. Fichas del 5 al 7 escritas, esperando sus fotos |

## Qué es

Lo que se repite de la primera serie no es la trama, sino la fórmula: **un sitio real donde
ocurre algo que no debería**, contado sin diálogo y sin explicar nada. Lo nuevo es que
alguien lo presencia siempre: el celador.

## El protagonista

Un celador de ronda nocturna, de unos 32 años, con gorra, chaqueta azul marino con bandas
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
.venv/bin/python serie_generar.py prompts/escenas/cel1_el-pedestal-vacio.json --ver-peticion
.venv/bin/python serie_generar.py prompts/escenas/cel1_el-pedestal-vacio.json --solo-acto 1
```

**Lo que la ficha puede pedirle a xAI**, con los nombres que usa su API:

| Campo de la ficha | Qué hace |
|---|---|
| `modelo` | `grok-imagine-video-1.5` |
| `duracion_s` | 1 a 15 segundos, frente a los 8 fijos de Veo |
| `formato` | `9:16` nativo, que es lo que pide TikTok |
| `resolucion` | `480p`, `720p` o `1080p` |
| `audio` | genera sonido, activado por defecto |
| `referencias` | imágenes que anclan al personaje; admite comodines para tomar la hoja entera. Si el comodín no encuentra ninguna, el script para |
| `foto` | fotograma de partida |
| `entrada` dentro de un acto | ese acto arranca de su propia imagen en vez de encadenar del anterior: un salto de lugar o de tiempo dentro del capítulo |
| `salida` | carpeta de los clips: `serie_celador/output`, fuera del `output/escenas` de Soatá |
| `prefijo` | prefijo de los archivos: `cel` genera `cel1_1_...mp4` y no pisa el `cap1_1_...mp4` de Soatá |

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
  `serie_placas.py --encima` lo hace: título sobre los primeros 3 s, «CONTINUARÁ» sobre los
  últimos 1,8 s, sin negros, y a 1080×1920.
- **Que cierre en bucle**: si el último fotograma se parece al primero, el video se repite sin
  costura.
- El gancho **no puede ser reconocer el sitio**: TikTok reparte por interés, no por
  geografía. Tiene que entenderse en dos segundos sin saber dónde es.
- **Zonas que tapa la interfaz**: abajo, el texto de la descripción y la música; a la derecha,
  los botones de me gusta, comentarios y compartir. Lo importante —el pedestal, la figura, el
  celador— va en el centro y en la mitad de arriba, y hay que comprobarlo en cada acto.
- **Actos de 6 s**: tres actos dan unos 18 s. Con 8 s el capítulo se iba a 24.

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

**La trama de la temporada**, decidida por el usuario: cada cierto número de noches, a la
misma hora, el celador se encuentra la misma escena —Bolívar hecho hombre, en bronce, yendo a
otro lugar de la ciudad— y lo sigue.

**Lo que hay detrás:** es un **ser de otro mundo que se funde con la estatua** y la usa como
vehículo para moverse. Busca un **antiguo transmisor escondido dentro de un objeto histórico**
—en algún museo o sitio de interés— que le permitirá **llamar a una nave de su planeta** para
que venga a rescatarlo. El objeto quedó abandonado en un viaje anterior de su especie a la
Tierra, hace cientos o miles de años.

**El objeto es la Balsa Muisca** del Museo del Oro, la pieza que representa la ceremonia de
El Dorado. Dentro de la ficción, los muiscas vieron llegar aquella luz, veneraron lo que la
especie dejó, y la leyenda de El Dorado es el recuerdo de esa visita. No se dice en pantalla.

**El celador trabaja en el Museo del Oro**: en el capítulo 1 iba camino de su turno. Por eso
tiene llaves y alarma a su cargo, y por eso ayudar le cuesta algo.

**Su arco**: de testigo a cómplice. Mira en el 1, el 2 y el 3; **apaga la alarma** en el 4,
**abre la vitrina** en el 5, y en el 7 **su linterna es la señal** que la nave necesitaba.

| Cap. | Título | Qué pasa | Qué hace el celador |
|---|---|---|---|
| 1 | El pedestal vacío | Niebla a las 3 am; Bolívar no está; la figura abre la Catedral con un mando | mira |
| 2 | La luz | Busca en la Catedral; la luz lo alcanza; despierta de día y Bolívar ha vuelto | pierde el conocimiento |
| 3 | El museo equivocado | Otra noche. La figura busca en el Museo Nacional; unas piezas muiscas laten azul: la pista | la sigue |
| 4 | El Salón de la Ofrenda | En su museo, el oro se enciende solo y la balsa responde. Salta la alarma | **la apaga** y deja ir a la figura |
| 5 | La balsa | La balsa sale flotando de la vitrina y la figura la lleva cerros arriba | **abre la vitrina**, y la sigue por Monserrate |
| 6 | La llamada | En la cima, la balsa lanza una columna de luz; las nubes giran, pero no baja nada | mira |
| 7 | El rescate | Baja la nave y el ser sale del bronce hecho luz. Al amanecer, Bolívar en su pedestal y a sus pies el mando, parpadeando | **hace la señal** con la linterna |

**Por qué cada cierta noche**: solo puede fundirse con el bronce cuando la niebla baja a la
plaza. Por eso cada capítulo empieza con niebla.

**Reglas para esta temporada:**

- **La figura nunca se ve de frente.**
- **La nave nunca entera**: luz, nubes que se abren y una sombra. La cúpula rígida del
  capítulo 7 de Soatá pareció "de Chespirito".
- **La balsa es pequeña**, así que actúa a través de su luz, que llena la sala.
- **Cómo volvió Bolívar a su pedestal no se explica.**

### Capítulo 1 — El pedestal vacío

Idea del usuario. Son las 3 de la madrugada y el celador va para su trabajo. Al cruzar la
Plaza de Bolívar hay un revuelo de palomas en medio de una niebla densa, y se alcanza a ver
que **Bolívar no está en su estatua**. Se adentra en la niebla y ve algo parecido a la
estatua que falta, que **con un mando que lleva en la mano abre la puerta de la Catedral** y
entra.

| Acto | Qué pasa | Cómo se sostiene |
|---|---|---|
| 1. Las palomas | Cruza la plaza con la linterna; una bandada alza el vuelo delante de él y se detiene | Catedral iluminada y faroles con halo: la niebla no puede tragarse el sitio |
| 2. El pedestal vacío | Se acerca al monumento y el haz sube por el pedestal: arriba no hay nadie, solo dos palomas | Lo pequeño no carga la acción, así que la cámara se acerca con él |
| 3. La puerta | Una silueta alta con capa y brillo de bronce, de espaldas, levanta el brazo; una luz roja parpadea, pita, y el portón se abre solo. Entra | El mando no se ve: se ve su efecto. Y el portón se abre sin que nadie lo toque |

**Decisiones:**

- **El mando lo lleva la figura**, no el celador. Es la lectura del texto; si es al revés,
  cambia el acto 3.
- **La figura nunca se ve de frente.** Es la regla que salvó Soatá: mostrar menos.
- **La foto de partida es de día y con gente.** Pedirle la noche a una foto de día ya falló en
  Soatá, así que conviene convertirla antes en una imagen nocturna, con niebla y sin gente,
  con la edición de imagen de Grok.

### Capítulo 2 — La luz

Idea del usuario. El celador se acerca a la puerta de la iglesia y ve dentro a **Bolívar
convertido en una estatua viva** que lo ilumina todo, como buscando algo. Al tratar de seguir
indagando **pierde el conocimiento** y despierta bajo el sol, al día siguiente, en medio de
palomas.

| Acto | Qué pasa | Cómo se sostiene |
|---|---|---|
| 1. El portón | Se asoma por el portón entreabierto. Al fondo de la nave, una figura de bronce con capa barre columnas y bancos con un haz de luz que le sale de la mano | Parte del último fotograma del capítulo 1. La figura, lejos y a contraluz |
| 2. La luz | La figura se detiene y gira el haz hacia el portón; la luz lo alcanza y llena el cuadro hasta quedar en blanco | El desmayo no se actúa: una caída es anatomía y contacto con el suelo |
| 3. El despertar | De día, tumbado en la plaza entre palomas, abre los ojos y se incorpora. La gente pasa sin mirarlo. Los portones cerrados y **Bolívar otra vez en su pedestal** | Arranca de la foto de día, que ya muestra justo eso |

**Decisiones:**

- **Del blanco a la mañana.** El acto 2 acaba en blanco, así que su último fotograma no sirve
  para encadenar; el acto 3 lleva su propia `entrada`.
- **Bolívar vuelve a su sitio** en el acto 3. No lo pidió el usuario, pero la foto de día lo
  trae y deja la duda: ¿lo soñó?
- **El interior de la Catedral lo inventa el modelo**, porque no hay foto. Se ve poco, solo
  donde pasa el haz. Para que sea fiel haría falta una foto del interior con licencia.

La propuesta anterior de cinco capítulos (palomas inmóviles, marcas, La Candelaria,
Monserrate, el relevo) queda **descartada**: no convencía.

## Lo aprendido

Reglas sacadas de la producción de los capítulos 1 a 4, con el error que enseñó cada una.
El detalle de cada acto está en los campos `leccion_*` y `version_elegida` de su ficha.

**Antes de escribir un capítulo nuevo, leer esta sección entera.** Cuesta menos que un clip.

### La imagen de partida manda

- **El video arranca exactamente en su imagen.** Lo que no deba verse en el primer fotograma
  —la estatua, la gente, el día— hay que quitarlo antes, editando la imagen. Si no, desaparece
  de golpe delante del espectador.
- **Lo que el acto vaya a mostrar tiene que estar ya ahí.** La niebla tapaba las escaleras de
  la Catedral y, al acercarse la cámara, el modelo las hizo aparecer de la nada.
- **El encuadre también lo manda la imagen, no el prompt.** Pedir "plano general" sobre un
  recorte cerrado no aleja la cámara: en el capítulo 3 hicieron falta cuatro intentos hasta
  entender que había que rehacer la imagen. Para abrir el plano, se monta la foto completa
  dentro del cuadro vertical y se le pide a Grok que rellene cielo y suelo.
- **Para que dos planos compartan un mueble o un objeto**, el plano amplio se genera a partir
  de un fotograma del plano corto: así la vitrina del capítulo 4 es la misma en los dos.
- **Al editar una imagen, un solo cambio cada vez.** Pedir a la vez "quita la estatua" y
  "despeja las escaleras" borró el monumento entero dos veces.
- **Quitar algo encoge lo que lo sostenía:** sin la estatua, el pedestal quedó más bajo.
  Revisar la imagen editada antes de gastar en video; cuesta $0,06 frente a $0,32-0,48.

### Quién sale y cómo se mantiene

- **Cada acto describe a quien sale en él.** Si solo va la descripción del celador, al resto
  el modelo lo simplifica: la figura subió al museo sin capa y, en la alarma, apareció una
  estatua dorada de mujer que no tenía nada que ver.
- **Cada personaje recurrente necesita su hoja de referencia.** El celador la tuvo desde el
  principio (`serie_celador/personaje/`); la figura de bronce no, y cambiaba en cada acto.
  La suya (`serie_celador/figura/`) se montó gratis con fotogramas de clips ya aprobados.
- **Un acto sin un personaje no lleva ni su descripción ni sus fotos.** Adjuntarlas invita al
  modelo a colocarlo en escena: el celador apareció dentro de la Catedral, linterna incluida,
  cuando debía estar fuera.
- **La ropa no se sostiene si choca con lo que el modelo "sabe".** "Celador" con "bandas
  reflectantes" se convierte, de frente, en un chaleco de alta visibilidad, por mucho que el
  texto y las seis referencias digan que van solo en las mangas.
- **De espaldas o de tres cuartos** evita la mayoría de problemas de cara y de ropa.

### Tamaño y encuadre de las figuras

- **Quien entra por el primer plano sale enorme.** Hay que hacerlo entrar por un borde lateral
  o por el fondo, y dar el tamaño explícito ("no más de un quinto de la altura del cuadro").
- **Caminar alejándose encoge a la figura solo**, por perspectiva, y de paso no se le ve la
  cara.
- **Un clip corto no da para dos recorridos**: en el capítulo 3, con la estatua y el celador
  en el mismo clip, siempre acababan juntos. Se arregló con un clip para cada uno.

### Objetos pequeños y efectos

- **Lo pequeño no carga la acción.** En plano general el modelo tiñe la sala entera de azul
  antes que encender unas vasijas que ocupan una décima parte del cuadro. El latido necesita
  su propio plano corto, con el objeto llenando el cuadro.
- **Un objeto con mucho detalle se conserva con tres cosas a la vez**: plano corto, sus fotos
  adjuntas como `referencias` —no solo como fotograma de partida— y que **lo único que cambie
  sea la luz**. Con eso la Balsa Muisca dejó de convertirse en otra pieza.
- **Si la acción necesita espacio que el cuadro no tiene, el modelo cambia el escenario.**
  "El haz sube por el pedestal hasta arriba", con lo alto ya en cuadro, convirtió el pedestal
  en un obelisco. Se pide la acción sobre lo que ya se ve y se prohíbe el cambio de forma.
- **Figura en movimiento más luz de color girando = deformación.** En la alarma del capítulo 4
  la capa se volvió tela roja y el cuerpo se deshizo. Si hace falta la luz, que la figura esté
  quieta o no esté.
- **Un fogonazo blanco a mitad de clip** deja al modelo sin arquitectura que respetar y se
  inventa otro lugar. El blanco va al final del clip, o se corta antes y se funde a blanco en
  el montaje, que sale gratis.

### Geografía y continuidad

- **La geografía que no se describe, se acorta.** Con "el monumento justo delante del portón",
  la figura fue en línea recta y se saltó la plaza y las escaleras.
- **No pedir sitios que no estén en la imagen.** Pedir "se va por la calle del costado" hizo
  que el modelo inventara una calle entera con soportales. Si algo debe quedar fuera, que el
  personaje salga por el borde del cuadro.
- **Los colores se contagian.** "Brillo verdoso de bronce" en la figura volvió verde el haz de
  la linterna; hay que decir el color de cada luz y, si hace falta, el que no puede tener.
- **El contacto sigue saliendo mal:** la figura apoya la mano en el portón en casi todos los
  intentos. Si importa, que la puerta se abra antes de que llegue.

### Montaje y formato

- **Grok devuelve cada clip con el tamaño que le toca** según su imagen de partida —400×736 y
  480×848 en el mismo capítulo—, y `concat` exige que todos midan igual: `une()` los escala al
  mayor.
- **Los actos pueden durar distinto.** 4 s para un remate, 5 s para una acción.
- **Para TikTok**, `serie_placas.py --encima`: título sobre los primeros 3 s, «CONTINUARÁ»
  sobre los últimos, sin negros, a 1080×1920. Con `--facebook`, el título ya está en el primer
  fotograma, que es la miniatura del Reel y no se puede cambiar después.
- **Se guardan todos los intentos** (`_previo`, `_previo2`...): en el acto 3 del capítulo 1 el
  usuario eligió primero una toma anterior y luego una posterior.

### Grok frente a Veo

| | Grok Imagine | Veo, en Soatá |
|---|---|---|
| Formato | vertical nativo 9:16, a 480p | apaisado, recortado después |
| Arquitectura | respeta bien la de la imagen, incluso con la cámara moviéndose | la reinventaba al oscurecer |
| Objetos con detalle | los repinta si son pequeños; se salvan con referencias | — |
| Cámara | tiende a acercarse, y a veces da un salto de plano | más quieta |
| Imágenes | genera y edita, $0,06 cada una | no se usó |
| Precio | $0,08 por segundo a 480p | COP 1.500 por clip de 8 s |
| Límite | ninguno visto; algún 429 por saturación | 10 al día |

### Lo que han costado los capítulos

| Cap. | Coste | Dónde se fue |
|---|---|---|
| 1 · El pedestal vacío | $3,70 | cuatro intentos del acto 3 |
| 2 · La luz | $2,52 | el celador aparecía dentro de la Catedral |
| 3 · El museo | $4,68 | seis intentos del acto 1; el latido en plano corto |
| 4 · La balsa | $4,52 | la balsa repintada; la vitrina y la figura deformadas |

Unos **$3,80 por capítulo**, frente a los $1,44 que calculé al principio.

### Forma de trabajo

1. **Primero la imagen, después el video.** Enseñar la imagen editada antes de gastar en clip.
2. **Un acto cada vez** con `--solo-acto`, revisado en una tira de fotogramas cada medio
   segundo antes del siguiente.
3. **Cada error se apunta en la ficha**, y lo que sirva para toda la serie, aquí.

## Fotos y créditos

Las fotos de Wikimedia Commons llevan licencia **CC BY-SA 3.0**: hay que citar al autor en la
descripción del video, y el video queda con la misma licencia. Los recortes verticales
(`*_vertical.jpg`) salen de estas mismas fotos.

| Archivo | Qué muestra | Dónde se usa | Autor y licencia |
|---|---|---|---|
| `plazaBolivar3.jpg` | Plano general: la estatua delante del portón central de la Catedral, con palomas | cap. 1, actos 1 y 3 (editada); cap. 2, acto 3 (tal cual) | Haakon S. Krohn, CC BY-SA 3.0, vía Wikimedia Commons |
| `plazaBolivar4.jpg` | La estatua desde abajo contra un cielo de tormenta. Tiene una persona grande en primer plano | cap. 1, acto 2, y cap. 7, acto 3 (editada) | Guaiquerí, CC0, vía Wikimedia Commons |
| `plazaBolivar2.jpg` | El pedestal de cerca, día de lluvia, con grafitis | reserva | Luis Alejandro Bernal Romero (Aztlek), CC BY-SA 3.0, vía Wikimedia Commons |
| `plazaBolivar5.jpg` | **Es Tunja, no Bogotá** | no se usa | — |
| `plazaBolivar1.jpg` | La Catedral de lejos | no se usa | **origen desconocido** |
| `Bolivar.jpeg` | La estatua de cerca | no se usa | marca de agua de Depositphotos |

**Las fotos no se usan tal cual casi nunca.** Un video arranca exactamente en su imagen de
partida, y estas son de día, con gente y con la estatua puesta. Cada ficha declara en
`imagenes_previas` qué versión necesita —de noche, con niebla, sin gente y sin estatua— y se
generan con la edición de imagen de Grok en `serie_celador/assets/editadas/` antes del video.

Línea para la descripción del video: *"Foto base: Haakon S. Krohn, CC BY-SA 3.0, vía
Wikimedia Commons"*.

## Pendiente

1. **Nombre de la serie**, para el título de los videos.
2. **Capítulo 2**: sacar el último fotograma del acto 3 del capítulo 1 (el comando está en su
   ficha) y probar la chaqueta sin "reflectantes".
3. **Fotos con licencia**, que las fichas esperan con estos nombres en `serie_celador/assets/`:

   | Archivo | Qué | Capítulos |
   |---|---|---|
   | `museo_nacional.jpg` | fachada del Museo Nacional | 3 |
   | `museo_del_oro.jpg` | Salón de la Ofrenda por dentro, o la fachada. Si no hay con licencia, se genera con Grok | 4 y 5 |
   | `monserrate_camino.jpg` | el sendero de piedra que sube a Monserrate | 5 |
   | `monserrate_cima.jpg` | el santuario y su explanada, mejor de noche | 6 y 7 |

   La arquitectura de esas fichas está escrita de memoria: hay que revisarla contra cada foto.
   En Depositphotos casi todo es editorial; Wikimedia Commons sirvió.
4. **Confirmar dónde se expone la Balsa Muisca** dentro del Museo del Oro. Las fichas la ponen
   en el Salón de la Ofrenda.
5. **Presupuesto real**: el capítulo 1 costó unos **$3,70** entre imágenes y clips. Con lo
   aprendido, calcular **$2,50-3,50 por capítulo** y unos **$20-25** para los seis que faltan.
6. **Rotar la clave de xAI**: se pegó en el chat.
