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

Siete líneas de investigación abiertas. Las cuatro primeras salieron de la
evidencia del baseline; OP-7 es una hipótesis exploratoria propuesta aparte.

| # | Línea | Prioridad | Techo medido |
|---|---|---|---|
| OP-3 | Modelo de generación | 🔴 Alta | 22 preguntas |
| OP-1 | Chunking estructural | 🟡 Media | 9 preguntas |
| OP-4 | Deduplicación del corpus | 🟡 Media | incluido en las 9 |
| OP-5 | Métrica de similitud | 🟡 Media | sin medir, costo ~1 línea |
| OP-6 | Discriminación en dos pasos | 🟡 Media | hasta 22, duplica latencia |
| OP-2 | Sanitización de fragments | 🟢 Baja | 0 casos hoy |
| OP-7 | RAG basado en nodos | 🔵 Exploratoria | sin medir, costo alto |


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

### OP-5 — Métrica de similitud del índice 🟡 **PRIORIDAD MEDIA**

Rama: `iteracion_1.5_similitud` · Plan: pendiente

La colección se crea sin especificar `hnsw:space`, por lo que ChromaDB usa **L2**
por defecto. `sentence-transformers.encode()` **no normaliza** los vectores salvo
que se le pase `normalize_embeddings=True`, y sin normalizar L2 y coseno **no
producen el mismo ranking**: L2 penaliza diferencias de magnitud que en un
embedding semántico no representan diferencia de significado.

Es la línea con mejor relación costo/beneficio del conjunto: el cambio es de una
línea y `scripts/medir_retrieval.py` lo evalúa en segundos, sin invocar al modelo.

**Métrica objetivo:** recall@6 ≥ 90% (actual 88%).
**Criterio de éxito:** cualquier mejora de recall sin regresión end-to-end.
**Riesgo:** ninguno relevante. Si no mejora, se revierte y queda documentado qué
métrica usa el índice — deuda técnica que la auditoría dejó abierta.

### OP-6 — Discriminación en dos pasos 🟡 **PRIORIDAD MEDIA**

Rama: `iteracion_1.6_dos_pasos` · Plan: pendiente · **Depende de:** OP-3

Separar en dos llamadas lo que el modelo no logra hacer en una: primero juzgar si
el contexto contiene la respuesta (salida binaria, sin redacción), y solo si es
afirmativo redactar la respuesta.

El baseline mostró que `llama3.2` falla precisamente en esa discriminación: ante
fragmentos vagamente relacionados asume que sirven y fabrica. Un juicio binario
aislado es una tarea mucho más simple que juzgar y redactar a la vez.

**Métrica objetivo:** alucinación ≤ 15% sin subir la abstención indebida.
**Criterio de éxito:** fallos de generación ≤ 15 con latencia aceptable.
**Riesgo:** duplica el número de llamadas al modelo y, por tanto, la latencia
(referencia: ~10,5 s por pregunta en el baseline).
**Condición:** ejecutar solo si OP-3 no alcanza su objetivo por sí sola. Si un
modelo de 7–8B resuelve la discriminación en un paso, esta línea pierde sentido.

### OP-7 — RAG basado en nodos 🔵 **HIPÓTESIS EXPLORATORIA**

Rama: `iteracion_1.7_nodos` · Plan: pendiente

Representar el corpus como un grafo de entidades y relaciones en lugar de una
colección plana de fragmentos, y resolver la consulta recorriendo el grafo en vez
de por similitud vectorial.

**Por qué el corpus se presta.** El dominio ya es estructural: entidades bien
delimitadas (SII, Municipalidad, SEREMI de Salud, Conservador de Bienes Raíces,
Notaría, Diario Oficial) unidas a trámites, documentos y plazos por relaciones
explícitas y estables — *SII otorga RUT*, *Municipalidad otorga Patente*,
*DOM emite Certificado de Zonificación*.

**Evidencia que la respalda.** El banco tiene una categoría completa de tipo
`delimitacion`, que son preguntas de "¿esto lo hace el SII o la municipalidad?".
Dos de los fallos de retrieval del baseline (PREG-078 y PREG-089) son justamente
de ese tipo: el dato vive en una tabla de instituciones que el embedding denso no
privilegia frente a prosa temáticamente parecida. Una arista de grafo responde eso
por estructura, no por similitud.

**Métrica objetivo:** resolver las preguntas de categoría `delimitacion` y
`factual` sobre instituciones sin depender del ranking vectorial.
**Criterio de éxito:** recall ≥ 95% en ese subconjunto, sin regresión en el resto.
**Riesgo:** es la línea de mayor costo del conjunto. Requiere extraer entidades y
relaciones del corpus, decidir el modelo de grafo y reescribir la capa de
recuperación. Conviene abordarla solo después de agotar OP-3, y acotada a un
subconjunto del corpus como prueba de concepto antes de comprometerse.

**Nota:** se evaluó y descartó una línea paralela sobre motores de base de datos
vectorial (Qdrant/FAISS/pgvector). Con 48 fragmentos el motor no es el cuello de
botella: cualquier implementación devuelve los mismos vecinos con el mismo
embedding. El único componente con valor medible de esa línea era la
**recuperación híbrida densa + léxica (BM25)**, pertinente porque varios fallos
del baseline involucran tokens exactos y raros ("Formulario 4415", "1 día hábil",
"2 meses"). Queda registrado por si se retoma.

---

## Criterio transversal de fusión

Toda rama hija debe:

1. Medir con `scripts/evaluar_banco.py` contra el mismo banco de 100 preguntas.
2. Comparar contra el baseline v1 (`resultados_v1.json`).
3. Documentar el resultado aunque sea negativo — ver `experimento_prompt_v2.md`
   como referencia de experimento fallido bien registrado.
4. No fusionar si los fallos de generación totales suben respecto al baseline.
