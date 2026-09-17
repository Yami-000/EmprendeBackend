# Análisis y Bifurcaciones — iteracion_1.0_baseline

Registra el análisis del baseline y las oportunidades (OP-N) identificadas, con
la recomendación de ramas hijas y criterios de éxito cuantitativo.

**Actualizado 2026-09-17** con los resultados de la primera corrida válida.
La priorización original (OP-1 chunking, OP-2 sanitización) se reordenó: las
mediciones muestran que ninguna de las dos ataca el modo de fallo dominante.

---

## Evidencia del baseline

Corrida completa de 100 preguntas (`resultado_1.0_e2e.md`):

```
RESPONDIBLES (50)     retrieval_hit@6 ....... 44/50 (88%)
                      abstuvo indebidamente . 12/50 (24%)
                      cobertura de datos .... 57%

NO RESPONDIBLES (50)  abstuvo (correcto) .... 33/50 (66%)
                      ALUCINO ............... 17/50 (34%)

ATRIBUCION            retrieval ..............  9
                      generacion ............. 22
```

**Techo de mejora por vía**, si cada una se resolviera por completo:

| Vía | Preguntas recuperables |
|---|---:|
| Generación (abstención indebida + alucinación) | 22 |
| Retrieval (chunking, k, embeddings) | 9 |

La generación pesa 2,4× más que el retrieval.

Se descartó además, con medición directa, que el problema fuera:
- contaminación del índice con documentos de la CMF (nunca estuvieron indexados),
- chunks duplicados (0 duplicados),
- desalineación de modelos de embedding entre ingesta y consulta (ambos 384 dims).

---

## Oportunidades

### OP-3 — Modelo de generación 🔴 **PRIORIDAD ALTA**

Rama: `iteracion_1.3_modelo` · Plan: `iteracion_1.3_modelo/plan_1.3.md`

`llama3.2` (3B) no discrimina de forma confiable si el contexto recuperado
responde la pregunta: ante fragmentos vagamente relacionados asume que sí y
fabrica. El experimento de prompt v2 (ver `experimento_prompt_v2.md`) confirmó
que no es un problema de redacción — reformular empeoró la alucinación de 34% a
78%. Es techo de capacidad del modelo.

**Métrica objetivo:** alucinación ≤ 15% manteniendo abstención indebida ≤ 12/50.

### OP-1 — Mejora de chunking 🟡 **PRIORIDAD MEDIA**

Rama: `iteracion_1.1_chunking` · Plan: `iteracion_1.1_chunking/plan_1.1.md`

Techo medido: 9 preguntas. El chunking actual corta por caracteres (800) y
produce una distribución muy desigual: `inicio_actividades_formalizacion_sii.md`
genera 17 chunks y acapara el 30,3% del top-6, mientras `patente_municipal.md`
tiene 1 solo chunk y aparece en el 1,7%.

Ejecutar **después** de OP-3: con un modelo más capaz, el valor marginal de
mejorar el retrieval cambia y conviene re-medir el techo antes de invertir.

### OP-2 — Sanitización de fragments 🟢 **PRIORIDAD BAJA**

Rama: `iteracion_1.2_sanitizacion` · Plan: `iteracion_1.2_sanitizacion/plan_1.2.md`

Mitiga prompt injection desde los documentos. No se observaron casos en el
baseline porque el corpus es de elaboración propia y controlada. Es una medida
preventiva, valiosa si en el futuro se ingestan documentos de terceros, pero no
mueve ninguna métrica actual.

### OP-4 — Deduplicación del corpus 🟡 **PRIORIDAD MEDIA**

Rama: `iteracion_1.4_corpus` · Plan: `iteracion_1.4_corpus/plan_1.4.md`

Dos documentos "paraguas" duplican contenido de otros cuatro y se llevan la
mitad del retrieval. Explica mejor el problema histórico de
"`tipos_sociedad_chile.md` no aparece en top-3" que la hipótesis de embeddings.

---

## Criterio transversal de fusión

Toda rama hija debe:

1. Medir con `scripts/evaluar_banco.py` contra el mismo banco de 100 preguntas.
2. Comparar contra el baseline v1 (`resultados_v1.json`).
3. Documentar el resultado aunque sea negativo — ver `experimento_prompt_v2.md`
   como referencia de experimento fallido bien registrado.
4. No fusionar si los fallos de generación totales suben respecto al baseline.
