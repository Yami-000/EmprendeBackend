# Resultado Fase 2 — Declarar las relaciones como predicados: **positivo**

**Fecha:** 2026-09-26 · **Rama:** `iteracion_1.10_relaciones_explicitas`
**Plan:** [`plan_1.10.md`](plan_1.10.md) · **Fase 1:** [`resultado_fase1.md`](resultado_fase1.md)
**Diagnóstico de origen:** [`hallazgo_relaciones_implicitas.md`](../iteracion_1.9_B1_juez_grande/hallazgo_relaciones_implicitas.md)

## Veredicto

**Pasa el corte, y la restricción que no se negocia queda intacta.**

```
nucleo duro ........  0 de 8  ->  5 de 8     corte >= 4       PASA
sensibilidad .......  18/29   ->  23/29                       PASA
especificidad ......  50/50   ->  50/50      piso 48/50       PASA
alucinacion ........  0/50    ->  0/50       tope 0%          PASA
recall@6 ...........  48/50   ->  48/50      piso 48/50       PASA
anclaje@6 ..........  29/37   ->  28/37      piso 29/37       NO PASA (-1)
```

**Un solo criterio falla, por un punto, y es atribuible a una única pregunta**
(PREG-118). Todo lo demás mejora o se mantiene. El índice queda en 28 chunks,
igual que el control.

## La variable

Seis frases-predicado agregadas al corpus, en tres archivos. **+11 líneas, 0
borradas:** ninguna línea de dato se tocó, ningún archivo se renombró.

```
antes    | Notaría | Escritura pública de constitución (régimen tradicional) |

después  La Notaría elabora la escritura pública de constitución del régimen
         tradicional: el notario público es el responsable de su elaboración.
         ...
         | Notaría | Escritura pública de constitución (régimen tradicional) |
```

La frase va **antes** de la tabla o de la lista, para caer dentro de los 256
tokens que lee el embedder. Verificado antes de reingestar: **las 8 citas de
anclaje siguen presentes** y el techo del banco sigue en 37 de 50.

**Restricción de adyacencia, que condicionó la ubicación.** `anclaje@k` compara
con `cita in norm(doc)`: una subcadena **contigua**. Dos de las citas del núcleo
duro abarcan varias líneas seguidas (PREG-064 dos viñetas; PREG-065 el encabezado
más dos viñetas), así que insertar la frase *entre* esas líneas habría destruido
la cita. En PREG-065 la frase tuvo que ir antes del encabezado `###`, no después.

## Retrieval

```
            recall (archivo)          anclaje (chunk)
  k         control -> Fase 2         control -> Fase 2
  1          21/50  ->  26/50          7/37  ->  12/37     <- la mejora
  3          41/50  ->  41/50         22/37  ->  22/37
  6          48/50  ->  48/50         29/37  ->  28/37     <- el costo
  8          48/50  ->  48/50         30/37  ->  30/37
```

**En k=1 el anclaje casi se duplica.** Es el efecto más grande que ha tenido el
retrieval en el proyecto a ese k, y el mecanismo es legible: la frase-predicado
contiene el verbo de la pregunta (`inscribe`, `elabora`, `emite`, `mantener`), así
que el chunk correcto sube al primer puesto. El corpus dejó de codificar la
relación solo como columna de tabla.

**El costo es una pregunta: PREG-118.** Su chunk de anclaje pasó del puesto 6 al
7, desplazado por el predicado de PREG-115 en el mismo archivo. En k=8 vuelve a
entrar, lo que confirma que es un deslizamiento de borde y no una pérdida.

## End-to-end

**Núcleo duro: 5 de 8.** Recuperadas PREG-065, 075, 080, 088 y 115. Las cinco
respuestas son correctas contra el `criterio_esperado` del banco.

Entre ellas **PREG-088**, que había resistido todo lo anterior: un juez de 7B (B1,
0 de 8), el prompt `flexible` (1 de 8) y la Fase 1 (0 de 8). El corpus ahora
afirma que la Notaría elabora la escritura, en vez de dejarlo implícito en una
columna llamada "Rol".

**Sensibilidad: 18/29 → 23/29**, sobre los **29 IDs exactos del control**. No se
regeneró el subconjunto a propósito: se deriva del índice, y regenerarlo habría
movido el denominador y roto la comparación.

```
ganadas (7) ... PREG-065, 068, 073, 075, 080, 088, 115
perdidas (2) .. PREG-070, PREG-118
```

**Dos de las ganadas no son del núcleo duro** (PREG-068 y 073): los predicados
ayudaron más allá de las preguntas que los motivaron.

**Las dos pérdidas tienen causas distintas, y conviene no confundirlas:**

- **PREG-118 es una regresión real.** Se respondía en el control y ahora abstiene.
  Es la misma pregunta del `anclaje@6`: su cita quedó en el puesto 7.
- **PREG-070 es inestabilidad del juez.** Su dato **sigue llegando íntegro**
  (`cobertura 0,5`, ancla `IVA` presente), así que el veredicto se movió por un
  cambio cosmético del contexto. Es la banda de ±6 ya documentada.

**Especificidad 50/50 y alucinación 0/50.** Sin pérdida de un solo punto. Era el
riesgo real de agregar texto afirmativo al corpus —hacer que un contexto
irrelevante parezca pertinente— y no se materializó: las frases afirman solo lo
que el corpus ya decía en forma de tabla.

## Lo que NO funcionó, y es lo interesante

**Tres de las ocho no se recuperan: PREG-010, PREG-064, PREG-084.** Y no es
retrieval. Verificado: el predicado **llega al contexto en las tres**, en el
**puesto 1** en PREG-010 y PREG-084.

```
PREG-010  predicado en el puesto 1  ->  el juez dice NO
PREG-084  predicado en el puesto 1  ->  el juez dice NO
PREG-064  predicado en el puesto 5  ->  el juez dice NO
```

**Las dos que preguntan "¿cuál es la diferencia entre...?" caen juntas** (064 y
084), y la tercera es una disyunción (*"¿se gestiona en el SII o en otra
institución?"*). Son preguntas **comparativas y disyuntivas**: no piden un dato
sino una relación entre dos datos. Una frase que declara la diferencia en prosa no
alcanza. **Es un mecanismo distinto del que esta iteración resolvió**, y es el
candidato natural para la próxima.

**Y esos dos predicados eran justo los que rompían el piso de `recall@6`.** En la
primera pasada se agregaron 8 predicados: `tipos_sociedad_chile.md` pasó de 2 a 3
chunks porque las dos frases empujaron la sección sobre el tope de 1400, el índice
subió a 29 chunks y ese chunk extra desplazó a PREG-110 y PREG-118 del puesto 6 al
7 — `recall@6` 47/50 y `anclaje@6` 28/37. Al quitar los dos predicados que **no
funcionan**, el índice volvió a 28 chunks, `recall@6` a 48/50, y la sensibilidad
**subió** de 22/29 a 23/29.

```
                        8 predicados    6 predicados
  indice .............  29 chunks       28 chunks
  recall@6 ...........  47/50           48/50
  anclaje@6 ..........  28/37           28/37
  nucleo duro ........  5 de 8          5 de 8
  sensibilidad .......  22/29           23/29
  especificidad ......  50/50           50/50
```

Las dos configuraciones se midieron completas. **Entra la de 6.**

El predicado de PREG-010 se conserva aunque no funcione: es neutro en retrieval
(`patente_municipal.md` sigue en 1 chunk y ocupa los mismos 5 slots del top-6) y
documenta qué se intentó.

## Reproducir

```bash
cd ai-service && python ingest.py && cd ..
python scripts/medir_retrieval.py          # 28 chunks, 48/50, 28/37

python scripts/evaluar_banco.py f2b_nucleo --dos-pasos --juez llama3.2 \
    --redactor llama3.2 \
    --ids PREG-010,PREG-064,PREG-065,PREG-075,PREG-080,PREG-084,PREG-088,PREG-115

# los 29 IDs del control, no regenerados
python scripts/evaluar_banco.py f2b_sens --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/dato_integro_k6_control_1.9.txt

python scripts/subconjunto_sin_respaldo.py > tests/dataset/sin_respaldo.txt
python scripts/evaluar_banco.py f2b_espe --dos-pasos --juez llama3.2 \
    --redactor llama3.2 --ids @tests/dataset/sin_respaldo.txt
```

**Trampa al regenerar los subconjuntos:** no redirigir `2>&1`. El script imprime
`banco: 100 preguntas | sin respaldo: 50` por stderr, y esa línea no lleva `#`, así
que `leer_ids` la tomaría como IDs. Es el mismo fallo que costó un relanzamiento
en la 1.9.

## La decisión que queda abierta

`anclaje@6` cierra en 28/37, un punto bajo el piso que fijó el plan. Es el único
criterio que falla. Contra eso: la sensibilidad sube +5 neto sobre el subconjunto
que ese piso existe para proteger, la especificidad y la alucinación quedan
perfectas, y el punto perdido se explica por una sola pregunta cuyo chunk está en
el puesto 7.

**El piso es un proxy del end-to-end, y el end-to-end mejoró.** La recomendación
es fusionar y dejar PREG-118 anotada como seguimiento. La alternativa honesta es
recuperarla primero moviendo el predicado de PREG-115 dentro de
`inicio_actividades_formalizacion_sii.md`, que es una variable nueva y otra vuelta
de medición.

## Qué sigue

1. **PREG-118**, barato: mover el predicado de PREG-115 dentro de su archivo y
   mirar solo `medir_retrieval.py`, que corre en segundos.
2. **Preguntas comparativas y disyuntivas** (PREG-010, 064, 084): el predicado en
   prosa no basta cuando la pregunta pide una relación entre dos datos. Mecanismo
   nuevo, y el candidato principal de la 1.11.
3. **Extender los predicados al resto del corpus**, con la lección aprendida:
   vigilar el conteo de chunks. Un predicado que parte una sección cuesta más de
   lo que compra.
4. **Pendiente de la Fase 1, sin medir:** el redactor puede abstenerse pese al `SI`
   del juez.
