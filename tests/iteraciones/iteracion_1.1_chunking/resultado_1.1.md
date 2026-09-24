# Resultado 1.1 — Chunking

**Fecha:** 2026-09-23
**Cambio bajo prueba:** `CHUNK_SIZE` 800 → 1400, `CHUNK_OVERLAP` 150 → 200 en `ingest.py`
**Arnés:** `scripts/evaluar_banco.py --dos-pasos`, juez y redactor `llama3.2` (3B), **`k=6`**
**Duración:** 1693 s (~28,2 min)

`k` se mantuvo en 6 a propósito, igual que en la 1.6, para que la comparación
aísle el chunking. La medición de retrieval dice que `k=8` rinde bastante más
(ver "Lo que queda sobre la mesa"), pero eso es una segunda variable.

## Resumen

Primera iteración en que **todas las métricas se mueven en la dirección correcta
a la vez**. El criterio de éxito del plan se cumple; las métricas objetivo, no.
El costo es tiempo: la corrida es un 44% más lenta.

## Métricas

| | v1 (1 paso) | 1.6 (2 pasos) | **1.1 (2 pasos + chunking)** | Objetivo |
|---|---:|---:|---:|---:|
| retrieval_hit@6 /50 | 44 | 44 | **46** | ≥ 47 |
| anclaje@6 /36 | 22 | 22 | **25** | ≥ 29 |
| Abstención indebida /50 | 12 | 25 | **21** | ≤ 15 |
| Cobertura de datos | 57% | 47% | **57%** | ≥ 65% |
| **Alucinación /50** | 17 (34%) | 0 (0%) | **0 (0%)** | ≤ 15% |
| Sensibilidad del juez | — | 26/50 (52%) | **30/50 (60%)** | — |
| **Especificidad del juez** | — | 50/50 | **50/50** | ≥ 80% |
| Fallos de generación | 29 | 25 | **21** | ≤ 12 |
| Duración | 17,5 min | 19,6 min | **28,2 min** | — |

## Resultado contra el criterio de éxito

> `anclaje@6` sube **y** la abstención indebida baja end-to-end, **sin** que la
> especificidad del juez caiga por debajo de 48/50.

| Condición | Resultado | |
|---|---|---|
| `anclaje@6` sube | 22/36 → 25/36 | ✅ |
| Abstención indebida baja | 25 → 21 | ✅ |
| Especificidad ≥ 48/50 | 50/50 | ✅ |

**Cumple.** Es la primera iteración del proyecto que lo hace.

Las *métricas objetivo* del plan, en cambio, no se alcanzan: recall@6 quedó en
92% contra un objetivo de 95%, `anclaje@6` en 69% contra 80%, y la abstención
indebida en 21 contra ≤15. La dirección es correcta, la magnitud es insuficiente.

## Atribución de las 21 abstenciones indebidas

Verificación estricta: la línea completa de la cita debe aparecer íntegra en el
contexto recuperado.

| Causa | 1.6 | **1.1** |
|---|---:|---:|
| Retrieval falló a nivel **archivo** | 4 | **4** |
| Retrieval falló a nivel **chunk** | 11 | **8** |
| Cita parafraseada en el banco, no verificable | 4 | **4** |
| El dato estaba íntegro y el juez negó | 5 | **4** |

**El chunking recuperó 3 de los 11 fallos a nivel de chunk.** Es exactamente
donde se esperaba que actuara, y no movió las otras categorías — lo que confirma
que la atribución es correcta.

Los cuatro falsos negativos que quedan del juez: PREG-010, PREG-067, PREG-084,
PREG-088. Su precisión sube de 45/50 a **46/50 (92%)**.

## La hipótesis original era falsa

El plan decía "cortar por encabezado markdown en lugar de acumular hasta 800
caracteres". **`_chunk_text` ya dividía por encabezados** —
`re.split(r'(?m)(?=^#{1,6}\s)', text)` — desde antes de esta iteración.

Se implementó de todos modos una reescritura estructural completa: un fragmento
por sección, sin solape, con la ruta de encabezados como prefijo y corte de
tablas repitiendo la cabecera de columnas. **Empeoró.**

## La ablación

El error de método fue cambiar cinco variables a la vez. La ablación las separa,
y cuesta ~10 s por variante porque no invoca al LLM:

| variante | chunks | k=6 rec/anc | k=10 rec/anc |
|---|---:|---|---|
| original (solape crudo de 150) | 48 | 44 / 22 | 47 / 27 |
| original **sin solape** | 42 | 42 / 22 | 45 / 25 |
| estructural, sin prefijo | 59 | 43 / **17** | 47 / 25 |
| estructural, con prefijo | 59 | 43 / **18** | 45 / **22** |

Dos conclusiones que contradicen el diagnóstico previo:

1. **Fragmentar más es peor.** Todas las variantes estructurales caen a 17-18.
2. **El solape no era el culpable.** Quitarlo no mejora nada (22 → 22). El
   diagnóstico de la 1.6 señalaba el solape crudo `chunk[-150:]` como la causa
   de que el 62% de los fragmentos empezara a mitad de frase. Eso es cierto como
   descripción, pero el efecto neto del solape es **positivo**: duplica el
   contenido de los bordes y da una segunda oportunidad de encontrar el dato.

Aislando el tamaño, con todo lo demás igual al esquema original:

| tope | solape | chunks | media | k=6 rec/anc | k=8 rec/anc |
|---:|---:|---:|---:|---|---|
| 800 | 150 | 48 | 639 | 44 / 22 | 47 / 25 |
| 1200 | 0 | 29 | 875 | 45 / 22 | 48 / 29 |
| 1400 | 0 | 26 | 976 | 44 / 26 | 48 / 29 |
| **1400** | **200** | **28** | **1014** | **46 / 25** | **48 / 31** |
| 1600 | 0 | 22 | 1154 | 43 / 23 | 48 / 33 |

**La causa real era el tamaño.** Con 800 caracteres la mayoría de las secciones
del corpus no cabía entera y el dato pedido quedaba partido entre dos fragmentos.

### Por qué 1400 y no 1600

`api.py` trunca cada fragmento a **1400 caracteres** al armar el prompt. Con un
tope de 1600, siete fragmentos superan ese límite y el recorte vuelve a partir
el dato justo antes de que el modelo lo lea — anulando la mejora que la métrica
de indexación mostraría. Con 1400/200 el fragmento más largo del corpus mide
1378. El tope del chunking está acoplado a ese truncado; subir uno exige subir
el otro.

## El costo: latencia

| | 1.6 | 1.1 |
|---|---:|---:|
| Latencia media del juez | 6,4 s | **12,3 s** |
| Latencia media del redactor | ~13 s | 15,5 s |
| Corrida completa | 19,6 min | **28,2 min** |

El juez casi duplica su costo. Es coherente con lo medido en la 1.6: el 98% de
su tiempo es *leer* el contexto, así que fragmentos un 59% más grandes se pagan
casi linealmente.

**Esto importa para el objetivo del proyecto.** Una consulta respondida cuesta
ahora ~28 s (12,3 del juez + 15,5 del redactor) en una GTX 1650. Para un bot de
Telegram es mucho. La mejora de calidad es real, pero hay un límite a cuánto
contexto se le puede dar a un modelo pequeño antes de que la espera sea el
problema.

## Instrumentos nuevos

- **`anclaje@k`** en `medir_retrieval.py`: mide si la cita del ground truth
  llega **íntegra** al contexto, no si llegó el archivo. Es lo que ve el juez.
- **`scripts/ablacion_chunking.py`**: compara configuraciones sobre colecciones
  temporales en memoria. Existe para que la próxima variante se mida antes de
  implementarse.

### El techo de `anclaje@k` es 36, no 50

14 de las 50 citas de anclaje del banco están **parafraseadas** y no existen
literalmente en ningún `.md`. Para esas preguntas ninguna técnica de chunking
puede dar positivo. Comparar el numerador contra 50 subestimaría el retrieval
en 28 puntos. El script imprime el techo en cada corrida.

Es deuda del banco, no del pipeline: son preguntas cuyo ground truth se redactó
resumiendo el documento en vez de citarlo.

## Lo que queda sobre la mesa

**Subir `k` de 6 a 8 es el siguiente paso más barato**, y está medido a nivel de
retrieval:

```
k=6   recall 46/50 (92%)   anclaje 25/36 (69%)
k=8   recall 48/50 (96%)   anclaje 31/36 (86%)     <- +6 preguntas
k=10  recall 48/50 (96%)   anclaje 32/36 (89%)
```

Es un cambio de una línea y sube el anclaje 17 puntos. **Pero encarece al juez
otra vez**, que ya está en 12,3 s. Hay que medirlo end-to-end antes de adoptarlo,
y decidir el punto de equilibrio entre calidad y latencia — no está claro que
sea `k` más alto.

Las 4 preguntas con fallo de retrieval a nivel de archivo (PREG-006, PREG-064,
PREG-075, PREG-116) no las arregla ni el chunking ni `k`: el documento
correcto no entra en el top. Esa es territorio de OP-4 (deduplicación del corpus)
o de OP-7 (RAG basado en nodos).
