# Resultado 1.15 — `CHUNK_SIZE`: 1400 ya era el óptimo. Refutada sin gastar LLM

**Fecha:** 2026-09-27 · **Rama:** `iteracion_1.15_chunk_size`
**Hipótesis:** la 1.14 levantó la ventana del embedder a 512 tokens, así que los
fragmentos **pueden** crecer sin volverse invisibles. Fragmentos más grandes y más
completos harían que los mismos `k=3` trajeran más dato, devolviendo el grupo B
—las 9 preguntas cuyo dato no llega— **sin tocar `k`**.

## Veredicto

**Refutada. `CHUNK_SIZE = 1400` es el óptimo, y lo es en las dos direcciones.**

Costo total: ~6 minutos de medición y **cero invocaciones al LLM**. El grupo B no se
recupera por acá.

## Por qué valía preguntarlo

El tope de 1400 se fijó en la 1.1 **por una razón que ya no aplica**: que el dato
llegara íntegro al juez, acoplado al truncado de `api.py`. Y la comparación que lo
justificaba (800 contra 1400) se hizo bajo `all-MiniLM-L6-v2`, donde un fragmento de
1400 caracteres **excedía la ventana de 256 tokens y quedaba parcialmente
invisible**. Es decir: esa comparación estaba confundida, porque las dos variantes no
se indexaban igual de completas.

Con e5 y 512 tokens los dos entran enteros. **Que el óptimo siguiera siendo 1400 no
era un dato, era una suposición.** Ahora está medido.

## El barrido, hacia arriba

```
tope/solape   chunks  media   >api  >ventana | k=3 rec/anc   k=6 rec/anc
1400 / 200        28   1042      0         0 |   45/32         48/35
1600 / 200        23   1226      9 !       0 |   47/32         47/34
1800 / 200        21   1323     10 !       1 !|   46/31         48/34
2000 / 200        20   1380     11 !       2 !|   46/30         50/35
2200 / 200        19   1442     10 !       5 !|   46/28         48/33
```

**El `anclaje@3` baja monótonamente: 32 → 32 → 31 → 30 → 28.** Fragmentos más
grandes son **menos específicos**, así que el correcto rankea peor. Y desde 1800 los
fragmentos empiezan a exceder otra vez la ventana del embedder, reintroduciendo el
problema que la 1.14 resolvió.

## El barrido, hacia abajo

```
tope/solape   chunks  media   >api  >ventana | k=3 rec/anc   k=6 rec/anc
 600 / 200        68    547      0         0 |   43/27         47/32
 800 / 200        51    662      0         0 |   44/27         48/33
1000 / 200        42    761      0         0 |   47/30         48/33
1200 / 200        33    915      0         0 |   46/30         47/33
1400 / 200        28   1042      0         0 |   45/32         48/35
```

**También peor.** El `anclaje@3` sube con el tamaño hasta 1400. Fragmentos chicos
parten el dato entre dos, que es exactamente lo que la 1.1 midió — **y esa conclusión
sí se sostiene bajo el embedder nuevo.**

## El solape

```
1400 /   0        26   1006      0         0 |   45/31         49/35
1400 / 100        28    989      0         0 |   45/31         48/36
1400 / 200        28   1042      0         0 |   45/32         48/35
1400 / 300        30   1043      1 !       0 |   46/31         48/34
1400 / 400        32   1056      1 !       0 |   46/30         47/33
```

200 es el mejor en `k=3`. Las diferencias son de 1 punto, así que tampoco hay nada
que ganar moviéndolo.

## Verificado en el pipeline real, porque la ablación tiene un sesgo

**`ablacion_chunking.py` no aplica el prefijo de palabras clave** que `ingest.py`
agrega al texto indexado, así que sus números absolutos no coinciden con
`medir_retrieval.py` (45/32 contra 46/30 en `k=3`). Solo sirve para comparar
variantes **entre sí**.

Por eso los dos contendientes se volvieron a medir con la ingesta real:

```
CHUNK_SIZE  chunks  k=3 rec/anc   k=6 rec/anc
      1000      42     44/28         48/33
      1400      28     46/30         49/36     <- optimo
      1600      23     46/30         48/36
```

**La conclusión de la ablación se sostuvo con las palabras clave puestas.** 1400 gana
o empata en todo.

## Lo que este resultado deja

**El grupo B no se ataca desde el chunking.** Las 9 preguntas cuyo dato no llega con
`k=3` son el precio de haber elegido `k=3` para evitar la fuga de PREG-045, y ese
precio **no se devuelve agrandando fragmentos**: agrandarlos empeora el ranking.

Lo que queda para el grupo B, ya en el terreno de lo que no se probó:

- **Recuperar con `k` variable**, más alto cuando el juez dice `NO` y hay margen. Es
  una segunda pasada de retrieval, no un cambio de chunking.
- **Un reordenador (*reranker*)** sobre un `k` mayor, para quedarse con 3 pero
  eligiéndolos mejor. Requeriría descargar un modelo.

Ninguna de las dos está medida y las dos son más caras que esta.

## Reproducir

```bash
python scripts/ablacion_chunking.py --topes 600,800,1000,1200,1400,1600,1800,2000,2200 \
    --solapes 200 --ks 3,6
python scripts/ablacion_chunking.py --topes 1400 --solapes 0,100,200,300,400 --ks 3,6
```

La ablación construye colecciones temporales en memoria: no toca el índice real y no
invoca al LLM. Se le agregaron en esta iteración los prefijos `query:`/`passage:` de
E5 —sin ellos medía otra cosa— y una columna `>ventana` con los fragmentos que
exceden los 512 tokens del embedder, que **desde la 1.14 es el límite que manda al
subir el tope**.
