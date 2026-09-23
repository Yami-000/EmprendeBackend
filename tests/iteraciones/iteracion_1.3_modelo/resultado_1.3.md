# Resultado 1.3 — Modelo de generación

**Fecha:** 2026-09-22
**Modelos evaluados:** `llama3.2:latest` (3B, baseline v1), `llama3.1:latest` (8B, Q4_K_M), `qwen2.5:7b` (Q4_K_M)
**Arnés:** `scripts/evaluar_banco.py`, mismo banco de 100 preguntas, mismo `k=6`, `num_predict=300`

## Resumen

Ningún modelo cumple el criterio de éxito del plan (alucinación ≤15% **y**
fallos de generación ≤15). Escalar de 3B a 7-8B mejora consistentemente la
extracción de datos cuando el modelo sí tiene la información, pero **no reduce
la alucinación de forma confiable** — en el mejor caso (llama3.1:8B) baja 2
puntos; en el peor (qwen2.5:7B) sube 8 puntos respecto al baseline.

## Métricas

| | v1 (3B) | llama3.1 (8B) | qwen2.5 (7B) | Objetivo |
|---|---:|---:|---:|---:|
| retrieval_hit@6 /50 | 44 | 44 | 44 | — |
| Abstención indebida /50 | 12 | **5** | **5** | ≤12 |
| Cobertura de datos | 57% | **69%** | 68% | ≥65% |
| Abstención correcta /50 | 33 | 34 | 29 | — |
| **Alucinación /50** | 17 (34%) | **16 (32%)** | **21 (42%)** | ≤15% |
| **Fallos de generación** | 29 | **21** | 26 | ≤15 |
| Fallos de retrieval | 6 | 6 | 6 | — |
| Duración corrida completa | 1050 s (~17,5 min) | 2496 s (~41,6 min) | 2258 s (~37,6 min) | — |

`retrieval_hit@6` y `fallos de retrieval` son idénticos en los tres porque no
dependen del modelo de generación, solo del embedding y el chunking (sin
cambios en esta iteración) — sirve como control de que la comparación es justa.

## Resultado por objetivo del plan

| Métrica objetivo | llama3.1 (8B) | qwen2.5 (7B) |
|---|---|---|
| Alucinación ≤ 15% | ❌ 32% | ❌ 42% |
| Abstención indebida ≤ 12/50 | ✅ 5/50 | ✅ 5/50 |
| Cobertura ≥ 65% | ✅ 69% | ✅ 68% |
| Fallos de generación ≤ 15 | ❌ 21 | ❌ 26 |

**2 de 4 en ambos casos.** Ninguno alcanza el criterio de éxito (los dos
objetivos críticos a la vez).

## El número agregado esconde el problema real

La alucinación total no cambia mucho, pero el **conjunto** de preguntas que
fallan sí cambia. Con llama3.1 (8B): 12 alucinaciones se repiten de v1, 5
desaparecen, **5 nuevas aparecen**. Con qwen2.5 (7B) aparecen **11 nuevas** que
v1 no tenía. Escalar el modelo no elimina el modo de fallo, lo reubica.

### Caso más grave: PREG-029 con qwen2.5 (7B)

> *"¿Qué diferencia existe entre una Liquidación y un Giro de impuestos?"*
>
> *"La liquidación es el proceso final que realiza **la empresa** ante el SII
> para determinar el saldo a favor o contra el contribuyente [...] un giro de
> impuestos se refiere al **cambio temporal en la tasa impositiva** aplicable a
> ciertos bienes o servicios durante un período específico."*

Doblemente falso: invierte quién liquida (es el SII, no la empresa) e inventa
una definición de "giro" que no existe — un giro es la orden de cobro emitida
tras la liquidación, no un cambio de tasa. Es más peligroso que un simple
"no sé" porque tiene estructura y tono de respuesta técnica correcta.

### Caso más grave: PREG-032 con llama3.1 (8B)

> *"¿Qué tribunal es competente contra liquidaciones del SII?"*
>
> *"El **Tribunal de Controversias Tributarias (TCT)**..."*

Esa institución no existe en Chile. El nombre real es Tribunales Tributarios y
Aduaneros (TTA). El modelo de 3B, ante la misma pregunta, se abstenía.

## Verificaciones que sí pasaron

- **Terminología chilena** (PREG-113, riesgo anotado en el plan): los tres
  modelos responden "Cédula de Identidad" sin mencionar "DNI". Sin regresión.
- **Retrieval:** idéntico en los tres, confirma que la comparación aísla
  correctamente la variable de generación.

## Bugs encontrados y corregidos durante esta iteración

1. **Detector de abstención con hueco.** `ABST` solo reconocía la frase
   canónica del prompt. Modelos más grandes razonan la ausencia de dato con
   frases como *"no se especifica en el contexto"* sin usar la frase exacta, y
   quedaban mal contados como alucinación. Corregido en `scripts/evaluar_banco.py`;
   reaplicado a los tres resultados ya guardados (v1: 0 cambios, 8B: 1 cambio,
   qwen: 0 cambios).
2. **`main()` sin guardia.** El script ejecutaba la evaluación completa al ser
   *importado*, no solo al ejecutarse directamente. Causó una corrida accidental
   con el modelo por defecto al reutilizar `abstuvo()` desde otro script.
   Corregido con `if __name__ == "__main__":`.

## Estimaciones de tiempo — corregidas con datos reales

La prueba de humo previa (3 llamadas con el modelo ya cargado en memoria)
subestimó la duración real por ~2,4×. Duración medida en corrida completa:

| Modelo | Estimado (humo) | Real |
|---|---:|---:|
| llama3.1 (8B) | 17-20 min | **41,6 min** |
| qwen2.5 (7B) | sin estimar | **37,6 min** |

Para futuras iteraciones: usar 35-45 min como referencia para modelos 7-8B en
esta GPU (GTX 1650, 4 GB, reparto CPU/GPU), no proyectar desde llamadas
aisladas con el modelo caliente.

## Conclusión

Escalar el tamaño del modelo (3B → 7-8B) mejora la fracción de "generación
cuando el modelo sabe" pero no toca el problema real: **el modelo no discrimina
de forma confiable si el contexto responde la pregunta**. Ante una pregunta sin
respaldo, en vez de reconocerlo, completa con conocimiento paramétrico —a veces
plausible, a veces con inversiones factuales o instituciones inventadas.

No hay evidencia de que un modelo aún más grande cambie este comportamiento
cualitativo por sí solo; el patrón se repite igual de fuerte a 7B, a 8B y a 3B.

## Siguiente paso

Pasar a **OP-6 — Discriminación en dos pasos**
(`tests/iteraciones/iteracion_1.6_dos_pasos/`): separar el juicio binario
("¿el contexto contiene la respuesta?") de la redacción. Es la vía que el plan
1.3 ya anticipaba como escalamiento si ningún modelo alcanzaba el objetivo por
sí solo, y ataca directamente el mecanismo de falla observado en los tres
modelos: no fallan al redactar, fallan al decidir si deben redactar.
