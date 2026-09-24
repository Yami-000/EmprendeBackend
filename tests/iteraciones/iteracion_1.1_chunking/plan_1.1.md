# Plan 1.1 — Chunking

**Prioridad:** 🔴 Alta · **Origen:** OP-1 de `ESTADO_INVESTIGACION.md`

> **Actualizado 2026-09-23.** Este plan ha cambiado de hipótesis dos veces. Se
> deja el historial visible a propósito: las dos versiones anteriores llevaban a
> trabajo que no habría servido.
>
> - **v1 (original):** chunking por tokens como vía principal contra la
>   alucinación. Descartada: el baseline mostró que el retrieval explica 9 de 31
>   fallos y la generación 22.
> - **v2 (2026-09-17):** "cortar por encabezado markdown en lugar de acumular
>   hasta 800 caracteres". **Descartada antes de implementar:** `_chunk_text` ya
>   divide por encabezados (`re.split(r'(?m)(?=^#{1,6}\s)', text)`). Implementarlo
>   habría sido reescribir algo que existe.

## Hipótesis vigente

El daño no lo hace la falta de estructura sino el **tamaño del fragmento**. Con
un tope de 800 caracteres la mayoría de las secciones del corpus no cabe entera,
así que el dato que pide la pregunta queda partido entre dos fragmentos y el
recuperador entrega solo una mitad.

## Métrica nueva: `anclaje@k`

`recall@k` se mide a nivel de **archivo** y es optimista: cuenta acierto si
alguno de los k fragmentos viene de un archivo que contiene la respuesta, aunque
ese fragmento no traiga el dato. Esta iteración introduce `anclaje@k`, que
acierta solo si la `cita_anclaje` del ground truth aparece **íntegra** en alguno
de los fragmentos recuperados. Es lo que realmente ve el juez.

**Techo de la métrica: 36 de 50.** Las otras 14 preguntas tienen una
`cita_anclaje` que el banco parafrasea y que no existe literalmente en ningún
`.md`, así que ninguna técnica de chunking puede darles positivo. No comparar el
numerador contra 50.

Ambas métricas las reporta `scripts/medir_retrieval.py`, que corre en segundos
sin invocar al LLM.

## Pasos

1. Medir el estado actual con `medir_retrieval.py`.
2. Ablación de variantes de chunking sobre colecciones temporales, aislando una
   variable a la vez.
3. Adoptar la configuración ganadora en `ai-service/ingest.py` y re-indexar.
4. Medir end-to-end con `evaluar_banco.py --dos-pasos`, **manteniendo `k=6`**
   para que la comparación contra la 1.6 aísle el chunking.

## Métricas objetivo

| Métrica | Antes | Objetivo |
|---|---:|---:|
| recall@6 | 44/50 (88%) | ≥ 95% |
| anclaje@6 | 22/36 (61%) | ≥ 80% |
| Abstención indebida (end-to-end) | 25/50 | ≤ 15/50 |
| Alucinación | 0% | se mantiene en 0% |

## Criterio de éxito

`anclaje@6` sube **y** la abstención indebida baja end-to-end, **sin** que la
especificidad del juez caiga por debajo de 48/50.

## Riesgo

Fragmentos más grandes significan más contexto por pregunta con el mismo `k`, lo
que encarece al juez (su costo es 98% lectura de contexto). Y un fragmento que
excede los **1400 caracteres** a los que `api.py` trunca cada fragmento volvería
a partir el dato justo antes de que el modelo lo lea: el tope del chunking no
puede superar ese límite sin subirlo también.
