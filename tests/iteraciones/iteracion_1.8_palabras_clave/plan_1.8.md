# Plan 1.8 — Palabras clave en el corpus

**Idea original:** Yami — colocar palabras clave en los documentos `.md`, unas 5
por documento, para que los fragmentos carguen ese vocabulario.
**Rama:** `iteracion_1.8_palabras_clave`, a crear desde `main`
**Estado:** acordado el 2026-09-24, al cerrar la 1.7

## Por qué esta línea

Es la destilación deliberada de lo único que ha funcionado dos veces por
accidente:

| Iteración | Qué se agregó al documento | Efecto en recall |
|---|---|---:|
| Piloto del corpus | encabezados con términos de las preguntas | +2 |
| 1.7 (grafo) | nombres de los nodos vecinos | +2 |

En ambos casos el mecanismo real fue **vocabulario nuevo y discriminativo**, no
la estructura que lo justificaba. Esta iteración lo hace a propósito.

## Lo que ya sabemos y condiciona el diseño

### La ventana del embedder es de 256 tokens

`all-MiniLM-L6-v2` tiene `max_seq_length = 256`. Los fragmentos actuales tienen
mediana 402 tokens: **24 de 28 exceden la ventana y un 33% del corpus es
invisible para el recuperador**. Una palabra clave más allá del token 256 no
existe para el retrieval.

**Consecuencia:** las palabras clave van arriba, y en **cada** fragmento, no solo
en el primero del documento.

### No hay "peso por palabra"

El modelo promedia todo en un vector de 384 dimensiones. Cinco palabras no
reciben peso propio: mueven el centroide del fragmento. Ponderación léxica real
sería **BM25**, que queda anotada como posible complemento posterior, no como
parte de esta iteración.

### Repetir texto redundante empeora

Medido en la 1.7: anteponer el título del documento a cada fragmento baja el
recall de 48 a 46 y el anclaje de 26 a 25. Repetir lo que el documento ya implica
acerca sus fragmentos entre sí y diluye lo propio de cada uno.

**Consecuencia:** las palabras clave deben ser **discriminativas** —lo que separa
a este documento de los otros doce— y aportar vocabulario que el documento no
tenga ya. "SII", "empresa" o "trámite" estarían en los trece y no discriminarían
nada.

## La trampa metodológica, escrita antes de empezar

**Si las palabras clave se eligen mirando el banco de preguntas, la mejora es
falsa**: sería ajustar al conjunto de prueba. Es el mismo error que el ground
truth poblado por script, que costó semanas detectar.

**Regla de esta iteración:** las palabras clave se derivan del **contenido del
documento**, como las escribiría alguien que no ha visto el banco. Se escriben
antes de mirar cualquier métrica, y no se ajustan después en función del
resultado. Si tras medir surge la tentación de cambiar una palabra para ganar una
pregunta, eso ya es ajuste al test y hay que declararlo como tal.

## Las dos variantes a medir

### A — Palabras clave en el texto del fragmento

Una línea de palabras clave al inicio de cada fragmento. Simple, pero el
vocabulario también lo lee el juez.

### B — Texto indexado distinto del texto mostrado

```
indexado   ->  5 palabras clave + encabezado + inicio del fragmento   (<=256 tokens)
mostrado   ->  el fragmento completo, 1400 caracteres                 (para el juez)
```

Las palabras clave trabajan al 100% en el recuperador y **no meten ruido en el
contexto del juez**. Ataca la ventana del embedder y la calidad del contexto por
separado, en vez de pelearlas con un mismo texto.

Implementación: pasar a `collection.add()` un `documents` y un `embeddings`
calculado sobre otro texto. Son pocas líneas en `ingest.py`.

## Pasos

1. Escribir 5 palabras clave por documento, derivadas del documento, **antes** de
   medir nada.
2. Implementar la variante A y medirla con `scripts/ablacion_chunking.py`.
3. Implementar el desacople de la variante B en `ingest.py` y medirla.
4. Comparar las dos contra el estado actual. Segundos, sin invocar al LLM.
5. Solo si alguna gana de forma clara en las métricas deterministas, validar
   end-to-end (~30 min).

## Métricas objetivo

| Métrica | Actual (1.7) | Objetivo |
|---|---:|---:|
| recall@6 | 48/50 | ≥ 49/50 |
| anclaje@6 | 26/37 | ≥ 30/37 |
| Fragmentos que exceden la ventana del embedder | 24/28 | — (lo mide la variante B) |

## Criterio de éxito

`anclaje@6` sube al menos 4 preguntas **sin** que baje el `recall@6`.

Se decide con las métricas deterministas. **No se usa el end-to-end para
decidir**: su banda de ruido es de ~6 preguntas y el efecto esperado es menor.

## Riesgos

- **Diluir en vez de enriquecer.** Palabras clave genéricas o redundantes empeoran,
  como mostró la prueba del título. El riesgo se mitiga exigiendo que sean
  discriminativas, y se detecta porque `recall@6` bajaría.
- **Ajuste al test.** Ver la sección de la trampa. Si el resultado es bueno y hay
  dudas, se puede reverificar derivando las palabras de la mitad de las preguntas
  y midiendo en la otra mitad.
- **Ruido para el juez** en la variante A. Es justamente lo que la variante B
  evita, y por eso se miden ambas.

## Después de esta iteración

**Sustituir el `SI`/`NO` del juez por una cita verificable** del fragmento donde
está el dato. Acordado con Yami. Motivo: el veredicto del juez se mueve en ~6 de
50 preguntas ante cambios cosméticos del contexto, y eso limita la capacidad de
medir cualquier mejora. Una cita es comprobable por código y no depende de que el
modelo mantenga una opinión estable.
