# Plan 1.9 — Hacer medible la decisión del juez, y atacar su sensibilidad

**Rama:** `iteracion_1.9_juez_con_cita` · **Abierta:** 2026-09-24
**Estado:** el diseño original quedó descartado en la Fase 0. Yami aprobó el
rediseño el 2026-09-24 y pidió abrir además una segunda vía.

> **Encuadre de Yami:** *"estamos experimentando a ver qué funciona mejor"*. Esta
> iteración tiene dos vías en paralelo y ninguna es apuesta segura. Lo que no se
> negocia es no romper lo que funciona: alucinación 0% y especificidad 50/50.

## Lo que ya se descartó, y por qué (Fase 0)

Sustituir el `SI`/`NO` del juez por una cita verificable. Detalle en
`resultado_fase0.md`. Resumen:

| Puerta | Resultado |
|---|---|
| ¿Transcribe literalmente un 3B? | **Sí, 10/10** con el prompt adecuado |
| ¿Mantiene la especificidad? | **No. 10 fugas de 10** |

El juez con cita **nunca dice NO**: siempre encuentra algo que citar, y 6 de esas
10 citas eran válidas pero irrelevantes. **Verificar que una cita exista no
sustituye al juicio.** Llevaría la especificidad de 50/50 a 0/50.

Se registró también que **no hay que poner ejemplos concretos en el prompt del
juez**: el modelo de 3B los copia como respuesta. Ese defecto hundía la primera
medición de 100% a 60%.

---

# Vía A — La cita audita el camino `SI`

```
paso 1   juez binario  ->  SI / NO              conserva la especificidad 50/50
paso 2   solo si dijo SI: "cita la línea"       hace auditable ese SI
paso 3   redactor
```

## Qué resuelve y qué no

**Resuelve:** la atribución determinista. Hoy no se puede saber si un `SI` está
justificado sin revisarlo a mano, y el veredicto del juez no es comparable con
`anclaje@k` porque miden cosas distintas. Con cita, el código compara la línea
citada contra la `cita_anclaje` del ground truth.

**No resuelve:** la sensibilidad. El binario seguirá negando 11 de 29 preguntas
cuyo dato tiene delante. Esta vía mide el problema con precisión; no lo arregla.
Por eso existe la vía B.

## Pasos

1. Añadir `JUEZ_PROMPT_BASES["cita"]` en `api.py` — **sin ejemplos concretos**.
2. En `evaluar_banco.py`, tras un `SI`, una segunda llamada que pida la cita. Solo
   en el camino `SI` (~25 de 100 preguntas), así el costo es acotado.
3. Verificar la cita con **la misma normalización** de `medir_retrieval.py` —sin
   tildes, sin viñetas, espaciado colapsado— o los números no serán comparables.
4. Calcular `cita_valida`, `cita_correcta` y `cita_irrelevante`.

## Métricas nuevas

| Métrica | Qué mide |
|---|---|
| `cita_valida` | la línea citada existe en el contexto (determinista) |
| `cita_correcta` | además coincide con la `cita_anclaje` del ground truth |
| `cita_irrelevante` | existe pero no responde: el `SI` no estaba justificado |

## Criterio de éxito

Se pueden clasificar los `SI` del juez en justificados y no justificados **sin
revisión manual**, y la especificidad sigue en ≥48/50.

Esta vía no tiene objetivo de sensibilidad: es instrumentación.

## Riesgo

Una segunda llamada por cada `SI` suma latencia al camino que ya es el caro (el
que además invoca al redactor). Medir: si el juez tarda 12,7 s y la cita añade
otros ~13 s, una consulta respondida pasaría de ~29 s a ~42 s. **Si sale así, la
cita queda como instrumento de medición fuera de línea y no entra en producción.**

---

# Vía B — Atacar la sensibilidad

El juez aprueba 18 de 29 preguntas cuyo dato llega íntegro (62%). Hay siete
hipótesis descartadas sobre por qué. Candidatas que **no** se han probado,
ordenadas por costo:

## B1 — Un modelo distinto solo para juzgar 🔴 prioridad alta

**Por qué es la más prometedora:** la iteración 1.3 concluyó que escalar el modelo
no ayuda, pero midió **generación en un paso**. Nadie ha medido un juez más
grande. Son tareas distintas, y el experimento B de la 1.6 probó lo contrario
(juez 3B + redactor 8B), no esto.

```
juez qwen2.5:7b  +  redactor llama3.2 (3B)
```

Es un hueco real en la evidencia. Prueba dirigida barata: las 29 preguntas cuyo
dato llega íntegro, ~7 min. Si aprueba claramente más de 18 con la misma
especificidad, es la vía.

**Tensión con la dirección del proyecto:** el objetivo es que corra en hardware
modesto. Un juez de 7B contradice eso en parte — pero solo el juez, no el
redactor, y el juez corre en el camino `NO` sin segunda llamada. Hay que medir
latencia real antes de descartarlo por principio.

## B2 — Descomponer la pregunta, no el contexto 🟡

El experimento A3 descompuso el **contexto** (un fragmento a la vez, recuperó
2 de 9). Nadie ha descompuesto la **pregunta**. Varias del banco piden dos cosas
a la vez: *"¿cuál es el plazo del Informe Sanitario y qué tipo de permiso es?"*
(PREG-110). Un juez que debe validar dos datos a la vez puede estar negando por
el que falta.

Prueba: partir las preguntas compuestas y juzgar cada parte. Barata sobre un
subconjunto.

## B3 — Umbral de similitud antes del juez 🟡

Descartar los fragmentos con distancia alta antes de pasarlos al juez, en vez de
darle siempre 6. Menos ruido y **menos contexto que leer**, así que podría bajar
la latencia a la vez. Se cruza con OP-5, que sigue pendiente: la colección usa L2
por defecto con vectores no normalizados, así que las distancias actuales no son
del todo interpretables. **Conviene hacer OP-5 primero.**

## B4 — Autoconsistencia del juez 🟢 costo alto

Varias pasadas y voto por mayoría. Atacaría directamente la inestabilidad de ~6
de 50 preguntas, pero multiplica la latencia del componente que ya es el cuello
de botella. Último recurso.

## Orden propuesto

1. **B1**, por ser un hueco real en la evidencia y barato de refutar.
2. **OP-5** (métrica de similitud), que es un cambio de una línea y desbloquea B3.
3. **B2**.
4. **Vía A** en paralelo, porque es instrumentación y no compite con las demás.

## Lo que no se negocia

Ninguna variante entra si la especificidad baja de 48/50 o si la alucinación sube
de 0%. Es el único resultado sólido del proyecto y el modo de fallo correcto para
un asistente sobre normativa tributaria.
