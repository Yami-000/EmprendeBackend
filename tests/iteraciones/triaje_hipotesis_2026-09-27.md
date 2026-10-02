# Triaje de hipótesis tras la 1.14 — qué queda realmente abierto

**Fecha:** 2026-09-27 · **Configuración:** `multilingual-e5-small`, `k=3`, corpus de la 1.10
**Motivo:** después de cinco iteraciones el mapa quedó desactualizado. Dos líneas
"pendientes" ya no lo están por razones distintas, y el conjunto de preguntas que
falla es **otro**.

> **Instantánea del 2026-09-27. Dos cosas de este documento ya no son ciertas,**
> y se dejan sin corregir porque es un registro fechado:
>
> - Dice que `/chat` sirve el pipeline de **un paso**. Dejó de ser cierto el
>   **2026-09-30** con la iteración 2.0, que lo portó a producción y lo verificó por
>   el endpoint.
> - Dice que quedan **dos** hipótesis abiertas. `CHUNK_SIZE` se refutó (1.15) y B2 se
>   confirmó (1.16): **las hipótesis del pipeline están cerradas.**
>
> El estado vigente está en el bloque de arranque de
> [`ESTADO_INVESTIGACION.md`](../../ESTADO_INVESTIGACION.md).

## Dos líneas que se cierran sin gastar una iteración

### OP-5 — Métrica de similitud del índice: **no-op, cerrada**

La línea decía que la colección usa **L2** por defecto y que
`sentence-transformers.encode()` **no normaliza**, de modo que L2 y coseno darían
rankings distintos. **Esa premisa es falsa para los modelos que usa el proyecto.**

Tanto `all-MiniLM-L6-v2` como `multilingual-e5-small` incluyen una capa
`Normalize`, así que los vectores salen **unitarios**. Y para vectores unitarios
`‖a−b‖² = 2 − 2·cos(a,b)`: el orden por distancia L2 y el orden por coseno son el
**mismo orden**, por construcción.

Comprobado, no solo argumentado:

```
vectores del indice: 28, dims 384
normas: min 1,000000  max 1,000000   -> unitarios
metrica del indice: None (L2 por defecto)

preguntas donde el top-6 por L2 y por coseno es IDENTICO:  50 de 50
```

**Cambiar `hnsw:space` a coseno no puede mover ningún número.** Sigue valiendo
declararlo explícitamente como *documentación* —la auditoría dejó esa deuda
abierta— pero **no es una hipótesis de mejora y no debe presupuestarse como tal.**

### OP-4 — Deduplicación del corpus: **premisa intacta, margen agotado**

La concentración que describía sigue ahí: dos documentos se llevan el **60%** de
los slots del top-6.

```
inicio_actividades_formalizacion_sii.md ....  98 de 300  (32,7%)
obligaciones_tributarias_y_tipos_sociedad.md  83 de 300  (27,7%)
```

**Pero su justificación era explicar el techo del retrieval, y ese techo ya no
existe:** `recall@6` está en 49/50 y `anclaje@6` en 36/37, con **un solo fallo de
cada tipo** (PREG-116 y PREG-106). Un arreglo perfecto compraría 1 o 2 preguntas.

Baja de prioridad. No está refutada: quedó **sin objeto**.

## El núcleo duro cambió, y eso reordena lo que vale

El núcleo duro histórico (8 preguntas) se definió sobre el índice de la 1.8. Con la
configuración actual el reparto es otro. De las **50 respondibles, el juez niega
16**, y se parten en dos grupos que piden trabajo distinto:

### Grupo A — el dato llega y el juez lo niega: **7 preguntas**

```
PREG-010  [delimitacion]  ¿...se gestiona directamente en el SII o en otra institución?
PREG-064  [conceptual]    ¿Qué diferencia existe entre una SA Cerrada y una SA Abierta?
PREG-083  [conceptual]    ¿Qué características tiene una Sociedad Colectiva Comercial?
PREG-084  [conceptual]    ¿Cuál es la diferencia entre los tipos de socios...?
PREG-104  [normativa]     ¿Cuál es el plazo para publicar el extracto de constitución...?
PREG-105  [normativa]     ¿En qué plazo debe inscribirse la empresa en el Registro...?
PREG-117  [conceptual]    ¿Cuál es la diferencia en responsabilidad y RUT entre Persona...?
```

**Cuatro de las siete son `conceptual`, y tres de esas cuatro preguntan
literalmente "¿cuál es la diferencia...?"** (064, 084, 117). Es exactamente el tipo
que la 1.12 caracterizó: **el juez de 3B verifica un hecho a la vez y no una
relación entre dos**.

**Eso convierte a B2 en la hipótesis de mayor valor del lado del juez**, y con un
techo mayor que el estimado antes: la 1.12 hablaba de 2 preguntas sobre un núcleo
de 3, y ahora el tipo que ataca domina 4 de 7.

### Grupo B — el dato no llega con `k=3`: **9 preguntas**

```
PREG-006, 061, 063, 068, 087, 103, 110, 112, 116
```

**Este grupo es el precio de haber elegido `k=3`.** Con `k=6` el `anclaje` es
36/37, así que a la mayoría les llegaría el dato — pero `k=6` filtra PREG-045. Se
cambiaron ~4 preguntas respondidas por 0 alucinaciones.

**Y ese precio es justamente lo que la hipótesis del `CHUNK_SIZE` podría devolver
sin tocar `k`:** fragmentos más grandes significan menos fragmentos y más completos,
así que con los mismos 3 llegaría más dato. Con la ventana en 512 tokens eso **por
primera vez es posible** — antes, agrandar el fragmento lo volvía parcialmente
invisible.

## Las dos hipótesis que quedan, y son complementarias

| | Ataca | Techo estimado | Costo | Riesgo |
|---|---|---|---|---|
| **`CHUNK_SIZE` mayor** | Grupo B (9) | parte del grupo B | barato: `medir_retrieval.py` en segundos | hay que subir el truncado de `api.py` a la vez, o el recorte anula la mejora |
| **B2, descomponer para el juez** | Grupo A (7), sobre todo las 4 `conceptual` | 3-4 preguntas | una llamada más por consulta | **nunca** descomponer para el retrieval ni el redactor, o puede tocar la especificidad |

**Una es de retrieval y la otra de generación, así que se pueden medir por separado
sin confundirse.** El orden natural es `CHUNK_SIZE` primero: es barato, se evalúa sin
invocar al LLM, y si devuelve parte del grupo B cambia el punto de partida de B2.

## Lo que no es una hipótesis

**Llevar el pipeline de dos pasos a producción no es una hipótesis: es trabajo de
ingeniería pendiente, y es lo más importante.** No hay nada que medir para saber si
conviene — está medido. `api.py` sirve `/chat` de un paso, que alucina 34%, y el bot
que usa la gente no tiene ninguna de las mejoras de 14 iteraciones.

Lo mismo con **OP-2 (sanitización de fragments)**: es una medida preventiva contra
prompt injection para cuando se ingesten documentos de terceros, no una hipótesis de
rendimiento. Sigue en prioridad baja con 0 casos observados.

## Reproducir este triaje

```bash
python scripts/medir_retrieval.py            # ocupacion del top-6 y fallos restantes
python scripts/medir_ventana_embedder.py
```

El reparto del grupo A y el grupo B sale de cruzar `resultados_v14_k3_full.json`
con la presencia de la cita de anclaje en el top-3, que es lo que distingue "el juez
falla" de "el dato no llegó". La prueba de L2 contra coseno compara los dos
ordenamientos sobre los embeddings del índice, que se leen con
`collection.get(include=['embeddings'])`.
