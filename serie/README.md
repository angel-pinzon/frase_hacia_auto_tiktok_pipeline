# Algo pasa en Soatá

Serie corta de terror y ciencia ficción ambientada en lugares reales de Soatá,
generada a partir de fotografías del pueblo. Sin diálogo y sin protagonista: el
pueblo es el personaje y todo se cuenta con lo que se ve en la calle.

## Por qué funciona

El gancho no es el terror, es **el lugar**. Contenido generado con IA hay
millones; una serie donde pasan cosas raras en una plaza que la gente reconoce,
no. Quien sea de Soatá se detiene aunque no le interese el género, y la comparte
porque es su plaza.

De ahí se derivan dos decisiones:

- **Siempre lugares reales**, fotografiados. Nada de escenarios inventados.
- **El nombre del pueblo va en el título**, para que el propio rótulo haga parte
  del trabajo de difusión.

## La historia

El portón de la iglesia es una puerta que se abre cada cierto tiempo. Cuando se
abre, algo pasa a través.

**La nave es el transporte; la iglesia es la puerta.** No vienen del espacio a
Soatá a merodear: vienen a atravesar. Por eso la nave es pequeña y se marcha
enseguida — es una lanzadera que deja pasajeros. Se entra por el cielo y se sale
por el portón, así que el pueblo no está siendo atacado, está siendo usado como
escala. De ahí que el título esté en presente: por Soatá **pasan** cosas.

**El pueblo lo sabe.** Lleva generaciones lidiando con ello: espera a que
termine, tapia el portón y sigue con su vida sin mencionarlo. La serie es una
sola noche de eso ocurriendo.

Nada de esto se explica nunca en pantalla. Se deduce.

## El arco

Ocho capítulos en **una sola noche**. La luz avanza con la historia, lo que da
una cuenta atrás implícita: algo tiene que pasar antes de que amanezca.

| # | Capítulo | Momento | Qué se ve | Qué ocurre en realidad |
|---|---|---|---|---|
| 1 | La horda ✅ | atardecer nublado | Una horda cruza la plaza frente a la iglesia y sigue de largo | No van a la iglesia: rondan, esperando a que se abra |
| 2 | La llegada ✅ | anochecer | Una nave aterriza en la plaza y bajan dos figuras, que se pierden hacia el pueblo. La nave sigue ahí, con los motores encendidos | La lanzadera deja pasajeros. No entran a ningún sitio: se dispersan |
| 3 | El rastro | noche | La plaza vacía, cosas tiradas, el carro abierto. La nave ya no está. Al fondo, una figura se quedó | La nave se fue mientras nadie miraba. La gente huyó, y uno no huyó |
| 4 | El llamado | noche cerrada | Esa figura gira la cabeza, el portón se abre solo y sale luz. Entra | La puerta funciona, y llama |
| 5 | Los que vuelven | madrugada | La horda regresa, ahora hacia la iglesia, y entra en fila | Esto era lo que esperaban toda la noche: es la salida |
| 6 | Las campanas | antes del alba | La plaza vacía, las campanas suenan solas y paran de golpe | La puerta se cierra. Se acabó el tránsito |
| 7 | El pueblo | primeras luces | Una calle con las puertas abiertas. Algo se mete en un zaguán | No todos alcanzaron a salir. Algo se quedó de este lado |
| 8 | El amanecer | sale el sol | Todo normal, salvo que el portón está tapiado con ladrillo | El pueblo lo cerró, como cada vez |

Los dos primeros ya están montados, en `output/serie/`.

**El final.** Sale el sol y la plaza está normal: gente caminando, tiendas
abriendo, nadie mirando la iglesia. El portón está tapiado con ladrillo, y el
ladrillo está viejo, con musgo, como si llevara cuarenta años ahí.

Ese es el remate: no lo taparon anoche, lo tapan cada vez. Ha pasado antes y
volverá a pasar. Por eso la serie se llama *Algo pasa en Soatá* en presente. El
plano final es un vecino que pasa frente al portón tapiado sin mirarlo siquiera.

Los capítulos 3 y 6 casi no tienen figuras en movimiento. Son los que más
inquietud crean y los más baratos de producir, porque el movimiento humano es lo
que peor se le da al modelo.

**El orden no es el que parece.** Los capítulos lentos —la plaza vacía, el que se
quedó— rinden mucho más *después* de que haya algo en juego. Por eso la nave va
de segunda y no en mitad de la serie: primero se establece que esto va en serio,
y luego se sostiene el silencio.

## Cómo se produce

Cada capítulo son dos o tres clips de 8 segundos generados con **Veo** en modo
imagen a video, encadenados y montados con FFmpeg.

**La continuidad se logra con el último fotograma.** Se extrae el último frame de
un clip y se usa como imagen de entrada del siguiente, así la escena continúa en
lugar de cortar:

```bash
ffmpeg -sseof -0.1 -i clip1.mp4 -vframes 1 -q:v 2 frame.jpg
```

**Las placas de serie** se añaden al final con una herramienta del proyecto, que
no gasta cuota ni saldo:

```bash
.venv/bin/python serie_placas.py output/escenas/cap2.mp4 \
    --numero 2 --titulo "El rastro" --vertical
```

Genera una entrada de 2.5 s con el nombre de la serie, el número y el título, y
un cierre con CONTINUARÁ. Con `--vertical` produce además la versión 9:16, que
encaja el apaisado sobre su propia imagen desenfocada en lugar de recortar.

**Las barras negras se quitan solas.** Veo rellena a 16:9 las fotos que no lo
son, y la de la plaza es 4:3: todos los clips vuelven como 960x720 útiles dentro
de un cuadro de 1280x720. En apaisado apenas se nota, pero en vertical esas
barras entran en la capa de primer plano y aparecen como dos cuñas negras sobre
el fondo desenfocado, que es justo lo que el encuadre 9:16 pretendía evitar. La
herramienta las detecta con `cropdetect` y las recorta antes de montar.

**Y lo inventado se deja fuera con `--recorte`.** Ver más abajo por qué hace
falta:

```bash
.venv/bin/python serie_placas.py clip.mp4 --numero 2 --titulo "La llegada" \
    --vertical --recorte 780:720:180:0
```

## Lo aprendido generando

**Una acción, no un ambiente.** Los primeros intentos fueron postales bonitas —
niebla, procesiones, amaneceres— y no retienen. Lo que funciona es que ocurra
algo con principio y final: el espectador se queda a ver cómo termina.

**Lo importante va en el primer acto.** Cada clip encadenado parte del anterior,
así que la deriva se acumula: el tercero ya va por la tercera generación y la
arquitectura empieza a deformarse.

**Y no solo se deforma: se inventa.** En la secuencia de la nave apareció pegado
al borde izquierdo un edificio de dos plantas con balcones de hierro que no
existe — en la foto real ese lado es de una sola planta, con tejado de teja. Y
las dos figuras se metían justo ahí.

Eso es más grave que un defecto visual, porque la serie entera se sostiene en que
el sitio sea reconocible: quien conozca la plaza nota al instante que esa casa no
es de allí. **Hay que revisar cada clip contra la foto original antes de darlo
por bueno**, con la foto al lado, y mirando sobre todo los bordes y el último
acto, que es donde más aparece.

Cuando pasa, casi siempre se arregla encuadrando más cerrado con `--recorte`, sin
gastar una generación. Y suele mejorar el plano: al cerrar el encuadre la
fachada gana tamaño. En el capítulo 2 se resolvió así, y de paso arregló el
guion — las figuras salen de cuadro y ya no hace falta explicar dónde entran.

**Los defectos con figuras aparecen al final del clip.** En el mismo capítulo, al
despegar la nave se llevaba pegado al costado medio cuerpo de una de las figuras,
fusionado con el fuselaje. Empieza a los 17.8 s de una secuencia de 24, y hasta
ahí todo estaba limpio: el modelo aguanta bien mientras la escena es estable y se
rompe cuando tiene que mover un objeto grande y una figura a la vez.

Por eso conviene **revisar el último tercio fotograma a fotograma**, y cortar con
`--hasta` en el último instante bueno en lugar de regenerar. En este caso el
capítulo acaba con la nave todavía posada, que además funciona mejor como
final — que se quede inquieta más que verla marcharse.

**Ser explícito con cantidades y destinos.** "Varias figuras" da cualquier cosa;
"EXACTAMENTE DOS figuras" funciona. Y el destino hay que describirlo por su
aspecto, no por su posición: "la casa blanca de tejado rojo, con el carro
estacionado frente a ella" en vez de "el edificio de la izquierda".

**Describir el recorrido paso a paso.** Que salgan del interior, bajen la rampa,
crucen la plaza y entren. Si se da por hecho, el modelo se lo salta.

## Costes y límites

| | Clips | Coste aproximado |
|---|---|---|
| Un capítulo de 3 actos | 3 | COP 4.500 |
| Con reintentos, realista | 4-5 | COP 7.000 |
| Temporada de 8 capítulos | 32-40 | COP 56.000 |

Cada clip de 8 segundos sale por unos **COP 1.500**.

**La restricción real no es el dinero, es la cuota.** El plan Tier 1 permite
**10 generaciones de video al día** y 2 por minuto, así que salen unos dos
capítulos diarios contando reintentos. Una temporada lleva cuatro o cinco días.
La cuota se renueva a medianoche del Pacífico, las 3 de la madrugada en Colombia.

Conviene afinar el prompt sobre papel antes de gastar una petición: un intento
fallido cuesta una de las diez.

## Publicación

**Formato del título**, igual en todos los capítulos:

```
ALGO PASA EN SOATÁ · Capítulo N: Título
Nuevo capítulo cada martes.
#AlgoPasaEnSoata #Soata #Boyaca
```

**Dónde.** La versión vertical va como Reel y a TikTok; la apaisada como
publicación de muro. Las historias desaparecen a las 24 horas, así que sirven
para avisar de capítulo nuevo, nunca para alojar la serie.

**Buena parte de la circulación será por WhatsApp**, de vecino en vecino, fuera
de cualquier algoritmo. Por eso las placas importan más de lo que parece: quien
reciba el capítulo 4 suelto sabrá que hay tres antes.

## Material

Fotografías necesarias, además de la plaza que ya está en `assets/`:

- Una calle del pueblo con zaguanes, para el capítulo 7.
- La plaza de día, para el capítulo 8.

Los clips generados viven en `output/escenas/` y los capítulos terminados en
`output/serie/`, ninguno versionado por peso. Los prompts sí se guardan en
`prompts/escenas/`: con ellos cualquier clip se puede volver a generar.
