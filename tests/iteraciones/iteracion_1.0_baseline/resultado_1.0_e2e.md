# Resultado 1.0 — Baseline End-to-End

**Fecha:** 2026-09-17
**Corrida:** 100 preguntas, pipeline completo, 1.050 s (~10,5 s por pregunta)
**Errores de conexión:** 0

> Nota: `resultado_1.0.md` (2026-09-06) quedó inutilizable — sus 20 filas son
> `ERROR: HTTPConnectionPool ... port=11400` porque el `ai-service` no estaba
> levantado. Este documento lo reemplaza como baseline válido.

## Configuración

| Parámetro | Valor |
|---|---|
| Modelo generador | `llama3.2:latest` (3B) |
| Embeddings | `all-MiniLM-L6-v2` (384 dims) |
| Índice | 48 chunks, 13 archivos, 0 duplicados |
| `k` | 6 |
| `temperature` / `top_p` | 0.0 / 0.1 |
| `num_predict` / `num_ctx` | 300 / 4096 |

## Resultados

### Respondibles (50)

| Métrica | Valor |
|---|---|
| Documento correcto en el top-6 | 44/50 (88%) |
| Se abstuvo indebidamente | 12/50 (24%) |
| Cobertura media de datos verificables | 57% |

### No respondibles (50)

| Métrica | Valor |
|---|---|
| Se abstuvo correctamente | 33/50 (66%) |
| **Alucinó** | **17/50 (34%)** |

## Atribución de los fallos

`retrieval_hit` se mide a nivel de archivo, así que los 8 casos inicialmente
clasificados como fallo de generación se re-verificaron comprobando si el
*chunk* recuperado contenía textualmente el dato esperado.

| Origen del fallo | Casos | Detalle |
|---|---:|---|
| Retrieval — archivo ausente del top-6 | 6 | PREG-006, 078, 089, 110, 112, 116 |
| Retrieval — archivo presente, chunk equivocado | 3 | PREG-010, 079, 109 |
| Generación — tenía el dato y se rindió | 5 | PREG-065, 076, 087, 104, 111 |
| Generación — alucinación | 17 | ver más abajo |

**Balance:** retrieval 9 · generación 22.

La generación pesa **2,4 veces más** que el retrieval.

## El problema dominante: 34% de alucinación

El system prompt indica de forma explícita qué responder cuando el dato no está
en el contexto, y aun así el modelo inventa en 1 de cada 3 casos.

Las alucinaciones tienen dos naturalezas distintas:

**Conocimiento paramétrico (respuesta correcta, origen inválido)**
- PREG-043 → responde "Código Tributario". Es correcto en el mundo real, pero no está en el corpus.
- PREG-042 → identifica la Defensoría del Contribuyente.
- PREG-013 → describe correctamente quiénes emiten boletas de honorarios.

Para un asistente tributario auditable esto sigue siendo un fallo: la respuesta
no es trazable a ninguna fuente y no hay forma de distinguirla de una invención.

**Invención pura (peligrosa)**
- PREG-016 → inventa un "Documento de Corrección de Factura Electrónica (FCE)",
  que **no existe** en la normativa chilena. La respuesta correcta es Nota de
  Crédito Electrónica.

## Lectura

Techo de mejora por vía, si cada una se resolviera por completo:

| Vía | Preguntas recuperables |
|---|---:|
| Arreglar generación (abstención + alucinación) | 22 |
| Arreglar retrieval (chunking, k) | 9 |

Optimizar el chunking rinde como máximo 9 preguntas y no toca el problema
principal. Antes de invertir ahí conviene atacar la generación.

## Siguiente paso propuesto

Dos experimentos baratos sobre el prompt, antes de cambiar de modelo:

1. **Mover la regla de abstención después del contexto recuperado.** Actualmente
   es la regla #3 de 4 y queda *antes* de los fragmentos. Los modelos pequeños
   pesan más lo último que leen.
2. **Reducir `num_predict`.** Con 300 tokens el modelo tiene espacio de sobra
   para elaborar; recortarlo limita la superficie de invención.

Si tras eso la alucinación sigue sobre el 20%, el siguiente paso es un modelo de
7–8B, que según el historial del proyecto es el cambio de mayor impacto esperado.
