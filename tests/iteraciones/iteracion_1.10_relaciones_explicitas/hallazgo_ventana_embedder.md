# Hallazgo — PREG-118 no se arregla moviendo el predicado: la causa es la ventana del embedder

**Fecha:** 2026-09-26 · **Rama:** `iteracion_1.10_relaciones_explicitas`
**Origen:** intentar cerrar la única deuda de la Fase 2
**Herramienta:** `scripts/medir_ventana_embedder.py` (nueva, corre en segundos)

Este documento no es un experimento con criterio de éxito: es el diagnóstico de
por qué la deuda barata de la Fase 2 **no era barata**, y deja cuantificado el
techo real del retrieval.

## Qué se intentó

La Fase 2 dejó `anclaje@6` en 28/37, un punto bajo el piso, por PREG-118: su chunk
de anclaje quedó en el puesto 7. El plan de acción era mover el predicado de
PREG-115 dentro del archivo.

Se intentó algo más directo: **darle a PREG-118 su propio predicado.** La pregunta
es *"¿Cuáles son los sitios web oficiales para realizar los trámites de
formalización?"* y la sección se llama `## Recursos Oficiales` — no contiene ni
*"sitios web"* ni *"formalización"*. Se agregó antes de la lista:

```
Los sitios web oficiales para realizar los trámites de formalización son los siguientes.
```

**No movió nada.** `anclaje@6` siguió en 28/37 y el chunk siguió en el puesto 7.

## Por qué no movió nada

El predicado **cae en el token 313 de su chunk**. El embedder lee 256.

```
chunk de inicio_actividades_formalizacion_sii.md: 1314 caracteres, 453 tokens
  '## Recursos Oficiales' empieza en el caracter 936 -> token 313
  ventana del embedder: 256
  -> INVISIBLE para el embedder
```

**El embedder nunca leyó la frase.** No es un problema de ubicación dentro de la
sección ni de redacción: la sección entera está fuera del vector de su propio
chunk. Ninguna frase que se agregue ahí puede cambiar el ranking.

## Son dos recortes distintos, y conviene no confundirlos

```
embedder (256 tokens)  ->  decide QUE chunks se recuperan
api.py   (1400 chars)  ->  decide QUE lee el juez de cada chunk recuperado
```

El segundo está documentado desde la 1.1. El primero estaba anotado como trampa en
`CLAUDE.md` pero **nunca se había cuantificado ni cruzado con `anclaje@k`**.

## La cuantificación

```
ventana del embedder: 256 tokens
indice: 28 chunks | tokens: mediana 382, min 140, max 495
chunks que exceden la ventana: 22 de 28
tokens invisibles para el retrieval: 3167 de 9954  (32% del corpus)

citas de anclaje DENTRO de la ventana: 23
citas de anclaje FUERA de la ventana:  14
   PREG-064, 067, 068, 073, 079, 081, 083, 084, 104, 105, 109, 111, 117, 118

anclaje@6 segun donde cae la cita:
  dentro de la ventana: 21/23  (91%)
  fuera de la ventana:   7/14  (50%)
```

**41 puntos de brecha.** Cuando la cita está dentro de la ventana, el retrieval la
encuentra casi siempre. Cuando está fuera, es una moneda al aire: se recupera solo
por carambola, porque el tramo visible del chunk resulta parecido a la pregunta.

**Las 8 citas que hoy no llegan íntegras con k=6 salen casi todas de ese grupo.**
De las 14 que caen fuera, 7 fallan; de las 23 que caen dentro, 2.

## Qué implica para el proyecto

**El tope de 1400 caracteres del chunking está peleado con la ventana del
embedder.** La 1.1 subió el tope a 1400 para darle más contexto al juez, y funcionó
para eso: el juez lee los 1400. Pero el vector de ese chunk se calcula con los
primeros ~256 tokens, así que **un tercio del corpus no se puede recuperar por su
propio contenido.**

Eso reinterpreta un resultado viejo. La 1.1 midió que fragmentar más era peor
(`anclaje` 22/36 → 18/36 con un fragmento por sección) y quedó como callejón sin
salida. Sigue siendo cierto que trocear a ciegas empeora, pero la razón no era que
los fragmentos grandes sean mejores: era que fragmentar cambiaba **dos cosas a la
vez** — lo que se indexa y lo que lee el juez. **Nadie ha probado desacoplarlas.**

## La hipótesis que deja abierta

**Indexar varias ventanas por chunk, sirviendo el chunk completo al juez.** En vez
de un vector por fragmento, varios vectores de ≤256 tokens que apunten al mismo
texto de 1400. El retrieval podría encontrar cualquier parte del fragmento y el
juez seguiría recibiendo el contexto completo. Requiere:

- `ingest.py`: emitir N entradas por chunk, con metadato del chunk padre.
- el camino de consulta: deduplicar por chunk padre, o `k=6` se gastaría en
  ventanas del mismo fragmento.

**No cuesta descargar nada** —es el mismo embedder— y `medir_retrieval.py` la
evalúa en segundos sin invocar al LLM. Es la primera vía en mucho tiempo que ataca
el retrieval y no al juez, con un techo estimable: las 7 preguntas que hoy fallan
teniendo la cita fuera de la ventana.

## Consecuencia para el PR de la 1.10

**`anclaje@6` se queda en 28/37, y ahora se sabe por qué.** No es una ubicación
mal elegida que se pueda corregir en una línea: es la ventana del embedder, y
arreglarlo es una iteración propia con cambios en `ingest.py`.

El predicado que se le agregó a PREG-118 **se revirtió**: era texto muerto, fuera
de la ventana, sin efecto medible.

## Reproducir

```bash
python scripts/medir_ventana_embedder.py
```
