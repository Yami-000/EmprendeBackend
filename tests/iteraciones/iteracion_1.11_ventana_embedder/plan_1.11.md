# Plan 1.11 — Embeber el fragmento completo, no solo sus primeros 256 tokens

**Rama:** `iteracion_1.11_ventana_embedder`, apilada sobre
`iteracion_1.10_relaciones_explicitas` (la 1.10 aún no está en `main`)
**Abierta:** 2026-09-26 · **Origen:** el hallazgo de la 1.10
**Leer antes:** [`hallazgo_ventana_embedder.md`](../iteracion_1.10_relaciones_explicitas/hallazgo_ventana_embedder.md)

> **Numeración provisional.** Se había reservado la 1.11 para las preguntas
> comparativas y disyuntivas. Esta vía se adelanta porque **se evalúa en segundos
> con `medir_retrieval.py`, sin invocar al LLM**, y porque resuelve la deuda que la
> 1.10 dejó abierta. Renumerar si molesta.

## El problema, cuantificado

```
ventana de all-MiniLM-L6-v2 ............ 256 tokens
tokens por chunk ....................... mediana 382, max 495
chunks que exceden la ventana .......... 22 de 28
tokens invisibles para el retrieval .... 32% del corpus

anclaje@6 con la cita DENTRO de la ventana .... 21/23  (91%)
anclaje@6 con la cita FUERA .................... 7/14  (50%)
```

El vector de cada fragmento se calcula con su primer tramo. Todo lo que viene
después **no influye en qué se recupera**, aunque el juez sí lo lea: `api.py`
sirve 1400 caracteres. Son dos recortes distintos y solo el primero decide el
ranking.

## Por qué esto no es "fragmentar más", que ya está refutado

La 1.1 midió que un fragmento por sección markdown empeora (`anclaje` 22/36 →
18/36) y quedó como callejón sin salida. **Sigue siendo cierto, y esta vía no lo
contradice:** trocear cambia dos cosas a la vez —lo que se indexa y lo que lee el
juez— y al juez le sirve el fragmento grande. Lo que nadie probó es **desacoplar
las dos cosas**, que es justo lo que la 1.8 ya dejó preparado:

```python
# ingest.py, iteración 1.8
# "el texto que se INDEXA no es el que se GUARDA"
```

La 1.8 usó ese desacople para meter palabras clave en el prefijo escaso. Esta
iteración lo usa para **eliminar la escasez del prefijo**.

## Variante A — promediar las ventanas (primero, es la barata)

**Variable única:** cómo se calcula el vector de cada fragmento en `ingest.py`.

En vez de embeber el fragmento entero y dejar que el modelo lo trunque a 256
tokens, se parte en ventanas de ≤240 tokens con solape, se embebe cada una y se
**promedia**, renormalizando a norma 1.

```
hoy      vector = embed(primeros 256 tokens)
después  vector = normalizar( media( embed(v) para cada ventana v ) )
```

**Por qué es sólido y no un truco:** el vector actual ya es un *mean pooling* sobre
los tokens que el modelo alcanza a leer. Promediar ventanas extiende ese mismo
promedio a todos los tokens del fragmento. La renormalización es necesaria porque
`all-MiniLM-L6-v2` trae capa `Normalize` y los vectores del índice son unitarios:
un promedio sin renormalizar no sería comparable.

**Lo que NO se toca:** nada del camino de consulta. Sigue habiendo **un vector por
fragmento**, así que `api.py`, `medir_retrieval.py` y `evaluar_banco.py` funcionan
sin cambios y `k=6` sigue significando seis fragmentos distintos. Es lo que hace
que esta variante sea segura y medible de inmediato.

**Riesgo documentado:** promediar **difumina**. Un fragmento que toca tres temas
pasa a tener un vector que no se parece mucho a ninguno. Puede subir el recall de
lo que estaba invisible y bajar la precisión de lo que ya funcionaba — y lo que ya
funcionaba son 21 de 23. **Es el riesgo principal y hay que mirar `k=1` y `k=3`,
no solo `k=6`.**

**Corte:** `anclaje@6` ≥ 30/37 sin que `recall@6` baje de 48/50. El control es
28/37 y 48/50; el techo estimable son las 7 preguntas que hoy fallan teniendo la
cita fuera de la ventana.

## Variante B — una entrada por ventana, deduplicando en la consulta

Solo si A no alcanza. En vez de promediar, se indexa **una entrada por ventana**,
todas apuntando al mismo texto de fragmento, y el ranking se queda con el mejor
resultado de cada fragmento (un *max* en vez de un *mean*). Preserva la precisión
en vez de difuminarla.

**Cuesta más y por eso va segunda:** hay que deduplicar por fragmento padre en
**tres** lugares —`api.py::_query_chroma`, `medir_retrieval.py` y
`evaluar_banco.py`— o `k=6` se gastaría en varias ventanas del mismo fragmento. Y
mientras no estén los tres, los números no son comparables entre sí.

## Orden y criterio

1. **Variante A**, medida solo con `medir_retrieval.py` y
   `medir_ventana_embedder.py`. Segundos, sin LLM.
2. Si A pasa el corte: las tres puertas end-to-end, en este orden — núcleo duro
   (~3 min), sensibilidad sobre los **29 IDs congelados del control** (~15 min),
   especificidad sobre las 50 sin respaldo (~20 min).
3. Si A no pasa: **Variante B**, con la misma secuencia.

**Lo que no se negocia, igual que siempre:** nada entra si la especificidad baja de
48/50 o si la alucinación sube de 0%.

## Advertencias heredadas

- **No regenerar el subconjunto de 29.** Se deriva del índice, y este experimento
  cambia el índice. Los IDs congelados están en
  `tests/dataset/dato_integro_k6_control_1.9.txt`.
- **El modelo de embeddings debe seguir coincidiendo** entre `ingest.py` y
  `api.py`. Esta iteración cambia *cómo* se embebe, no *con qué*: `all-MiniLM-L6-v2`
  en ambos lados. Si eso divergiera, los vectores del índice y los de la consulta
  dejarían de ser comparables.
- **No se descarga nada.** Es el mismo embedder ya en caché.

## Lo que NO hay que proponer en esta línea

- **Cambiar a un embedder de ventana más grande.** Requeriría descargar un modelo,
  y está prohibido sin aprobación. Queda anotado como pendiente de decisión.
- **Subir `CHUNK_SIZE`.** Empeora el problema: más tokens fuera de la ventana.
- **Fragmentar por sección.** Refutado en la 1.1, y esta vía existe precisamente
  para no tener que hacerlo.
