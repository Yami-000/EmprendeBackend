# Estado de la investigación — pipeline RAG

**Este archivo es el mapa del proyecto.** Registra qué se probó, qué funcionó,
qué se descartó y con qué evidencia. Léelo antes de proponer cualquier cambio al
pipeline: buena parte de las ideas plausibles ya se midieron y fallaron, y están
documentadas abajo con el número que las refutó.

> **Regla de ubicación.** Vive en la raíz y se fusiona a `main` apenas se cierra
> una iteración, **por separado del código de esa iteración**. No debe volver a
> quedar dentro de `tests/iteraciones/iteracion_X.X_*/`: estuvo en la carpeta de
> la 1.0 y quedó atrapado en un PR sin fusionar, de modo que las ramas 1.6 y
> posteriores citaban oportunidades (OP-6) que no existían en su árbol.

**Última actualización:** 2026-09-23, tras cerrar la iteración 1.6.

---

## Estado actual del sistema

Mejor configuración medida — **pipeline de dos pasos con `llama3.2` (3B) en
ambos roles**, iteración 1.6:

```
RESPONDIBLES (50)     retrieval_hit@6 ........ 44/50 (88%, medido por archivo)
                      abstuvo indebidamente .. 25/50
                      cobertura de datos ..... 47%

NO RESPONDIBLES (50)  ALUCINO ................   0/50 (0%)

JUEZ                  especificidad .......... 50/50 (100%)
                      precisión real ......... 45/50 (90%)

Duración .............................. 19,6 min
```

**Dirección estratégica:** hacer rendir al modelo de 3B cambiando la
arquitectura, no sustituirlo por uno más grande. Un sistema que corre en
hardware modesto es el objetivo del proyecto, no una limitación a superar.

---

## Las siete líneas de investigación

| # | Línea | Estado | Evidencia |
|---|---|---|---|
| OP-3 | Modelo de generación | ❌ **Refutada** | 1.3 — escalar a 7-8B no baja la alucinación |
| OP-6 | Discriminación en dos pasos | ✅ **Confirmada** | 1.6 — alucinación 34% a 0% |
| OP-1 | Chunking estructural | 🔴 **Prioridad alta** | 1.6 — 19 de 25 fallos vienen de aquí |
| OP-5 | Métrica de similitud | ⏳ Pendiente | sin medir, costo ~1 línea |
| OP-4 | Deduplicación del corpus | ⏳ Pendiente | incluido en el techo de retrieval |
| OP-7 | RAG basado en nodos | 🔵 Exploratoria | sin medir, costo alto |
| OP-2 | Sanitización de fragments | 🟢 Baja | 0 casos observados |

---

## Callejones sin salida — no repetir

Cada una de estas ideas se midió y no funcionó. Reintentarlas sin un argumento
nuevo es retrabajo.

| Idea | Qué pasó | Dónde está |
|---|---|---|
| **Escalar el modelo de generación** | `llama3.1:8b` deja la alucinación en 32% y `qwen2.5:7b` la sube a 42%, contra 34% del 3B. Cuesta 2,4x el tiempo de corrida | `iteracion_1.3_modelo/resultado_1.3.md` |
| **Reformular el system prompt (v2)** | Mover la regla de abstención a un cierre tras el contexto subió la alucinación de 34% a **78%** | `experimento_prompt_v2.md` |
| **Recalibrar el prompt del juez (A2)** | Quitar el sesgo *"ante cualquier duda responde NO"* recupera **1 de 9** casos | `iteracion_1.6_dos_pasos/resultado_1.6.md` |
| **Juzgar fragmento por fragmento (A3)** | Descomponer el contexto en 6 juicios de ~220 tokens recupera **2 de 9** | `iteracion_1.6_dos_pasos/resultado_1.6.md` |
| **Juez 3B + redactor 8B (experimento B)** | Descartado sin correr: el redactor ya responde en 25 de las 26 veces que se le habilita. El problema no está ahí | `iteracion_1.6_dos_pasos/resultado_1.6.md` |
| **Contaminación del índice con documentos de la CMF** | Nunca estuvieron indexados. `ingest.py` solo lee `docs/sii/`. El daño estaba en el ground truth, no en ChromaDB | `Bitacora.md` 2026-09-17 |
| **Chunks duplicados en ChromaDB** | 0 duplicados. La sospecha venía de que `collection.add()` acumulaba entre ingestas; ya es idempotente | `Bitacora.md` 2026-09-17 |
| **Desalineación de embeddings ingesta/consulta** | Ambos usan 384 dims. Era un riesgo real (`nomic-embed-text` con respaldo silencioso) pero coincidían por accidente. Ya está fijado | `Bitacora.md` 2026-09-17 |
| **Cambiar de motor de base vectorial** (Qdrant/FAISS/pgvector) | Con 48 fragmentos el motor no es el cuello de botella: cualquier implementación devuelve los mismos vecinos con el mismo embedding | ver OP-7, nota final |

### Advertencias de método

- **`retrieval_hit@k` se mide a nivel de archivo y es optimista.** Cuenta acierto
  si alguno de los 6 fragmentos viene de un archivo que contiene la respuesta,
  aunque ese fragmento concreto no traiga el dato. El 88% nominal esconde un
  recall a nivel de *chunk* bastante peor. Las coberturas de las iteraciones 1.0
  y 1.3 (57%, 69%, 68%) están infladas por la misma razón: en modo de un paso el
  modelo completaba con memoria paramétrica lo que el chunk no traía.
- **Verificar la presencia de un dato buscando cifras sueltas produce falsos
  positivos.** Un `27%` puede aparecer en el contexto por otra razón. Exigir que
  la línea completa de la cita aparezca íntegra cambió el diagnóstico de la 1.6
  de 9 falsos negativos del juez a 5.
- **Un experimento, una variable.** El prompt v2 cambió dos cosas a la vez y
  costó una corrida entera poder atribuir el efecto.

---

## Detalle por línea

### OP-1 — Chunking estructural 🔴 **PRIORIDAD ALTA**

Rama: `iteracion_1.1_chunking` · Plan: `iteracion_1.1_chunking/plan_1.1.md`

`_chunk_text` en `ingest.py` acumula por **caracteres** (`chunk_size=800`,
`chunk_overlap=150`) y corta frases a la mitad. La 1.6 dio la evidencia directa
que antes faltaba:

- 19 de las 25 abstenciones indebidas son atribuibles a retrieval y chunking;
  solo 5 al juez.
- **PREG-076** es el caso testigo. El fragmento recuperado empezaba en
  `"...régimen de renta atribuida; 27% para régimen semi-integrado"`: el corte se
  llevó el `25%` y el sujeto de la oración. Ningún componente posterior puede
  reconstruir eso.
- La distribución de chunks es muy desigual:
  `inicio_actividades_formalizacion_sii.md` genera 17 chunks y acapara el 30,3%
  del top-6, mientras `patente_municipal.md` tiene 1 solo y aparece en el 1,7%.

El techo de 9 preguntas que la 1.0 asignó a esta vía se calculó con
`retrieval_hit` a nivel de archivo. **El techo real es mayor.**

**Propuesta:** cortar por encabezados markdown en vez de por longitud, de modo
que cada chunk sea una unidad semántica completa (un trámite, una tabla, un
requisito). Medir con `scripts/medir_retrieval.py` — segundos, sin invocar al
modelo — antes de comprometerse a una corrida end-to-end de 20 min.

### OP-6 — Discriminación en dos pasos ✅ **CONFIRMADA**

Rama: `iteracion_1.6_dos_pasos` · Resultado: `iteracion_1.6_dos_pasos/resultado_1.6.md`

Separar en dos llamadas lo que el modelo no logra en una: primero un juez binario
decide si el contexto contiene la respuesta, y solo si dice `SI` se invoca al
redactor.

**Resultado: alucinación de 34% a 0%**, con especificidad perfecta (50/50) y
*más rápido* que el baseline de un paso (19,6 min contra 17,5), porque 74 de 100
preguntas se resuelven por el camino `NO` sin segunda llamada.

El riesgo que anticipaba el plan — que el juez heredara el mismo problema un
nivel arriba — no se materializó. La hipótesis de que duplicaría la latencia
tampoco: el juez cuesta ~6,4 s, de los cuales el 98% es leer el contexto, pero
evitar la segunda llamada compensa de sobra.

Queda implementado **solo en el arnés de evaluación**. `api.py` conserva el
endpoint `/chat` de un paso: llevarlo a producción es trabajo pendiente.

### OP-3 — Modelo de generación ❌ **REFUTADA**

Rama: `iteracion_1.3_modelo` · Resultado: `iteracion_1.3_modelo/resultado_1.3.md`

La hipótesis era que `llama3.2` (3B) no discrimina si el contexto responde la
pregunta por techo de capacidad, y que un modelo de 7-8B lo resolvería.

Escalar mejora la **extracción** cuando el modelo sí tiene la información
(cobertura 57% a 69%) y reduce la abstención indebida (12 a 5), pero **no
resuelve la alucinación**: 32% con `llama3.1:8b`, 42% con `qwen2.5:7b`. Ninguno
cumplió el criterio de éxito.

Lo que sí dejó esta iteración: la evidencia de que el problema es arquitectónico
y no de capacidad, que es justamente lo que la 1.6 confirmó.

### OP-5 — Métrica de similitud del índice ⏳ **PENDIENTE**

Rama: `iteracion_1.5_similitud` · Plan: pendiente

La colección se crea sin especificar `hnsw:space`, así que ChromaDB usa **L2** por
defecto. `sentence-transformers.encode()` **no normaliza** salvo que se le pase
`normalize_embeddings=True`, y sin normalizar L2 y coseno **no producen el mismo
ranking**: L2 penaliza diferencias de magnitud que en un embedding semántico no
representan diferencia de significado.

Mejor relación costo/beneficio del conjunto: el cambio es de una línea y
`medir_retrieval.py` lo evalúa en segundos.

**Métrica objetivo:** recall@6 ≥ 90% (actual 88%).
**Riesgo:** ninguno relevante. Si no mejora, se revierte y al menos queda
documentado qué métrica usa el índice — deuda que la auditoría dejó abierta.

### OP-4 — Deduplicación del corpus ⏳ **PENDIENTE**

Rama: `iteracion_1.4_corpus` · Plan: `iteracion_1.4_corpus/plan_1.4.md`

Dos documentos "paraguas" duplican contenido de otros cuatro y se llevan la mitad
del retrieval. Explica mejor el problema histórico de
"`tipos_sociedad_chile.md` no aparece en top-3" que la hipótesis de embeddings.

Se solapa con OP-1: conviene medir el chunking estructural primero y re-evaluar
cuánto queda de este efecto después.

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
`delimitacion` — preguntas de "¿esto lo hace el SII o la municipalidad?". Dos de
los fallos de retrieval del baseline (PREG-078 y PREG-089) son de ese tipo: el
dato vive en una tabla de instituciones que el embedding denso no privilegia
frente a prosa temáticamente parecida. Una arista de grafo responde eso por
estructura, no por similitud.

**Riesgo:** la línea de mayor costo del conjunto. Requiere extraer entidades y
relaciones, decidir el modelo de grafo y reescribir la capa de recuperación.
Acotarla a un subconjunto del corpus como prueba de concepto antes de
comprometerse.

**Nota.** De la línea descartada sobre motores vectoriales, el único componente
con valor medible era la **recuperación híbrida densa + léxica (BM25)**,
pertinente porque varios fallos del baseline involucran tokens exactos y raros
("Formulario 4415", "1 día hábil", "2 meses"). Queda registrado por si se retoma.

### OP-2 — Sanitización de fragments 🟢 **PRIORIDAD BAJA**

Rama: `iteracion_1.2_sanitizacion` · Plan: `iteracion_1.2_sanitizacion/plan_1.2.md`

Mitiga prompt injection desde los documentos. No se observaron casos porque el
corpus es de elaboración propia. Medida preventiva, valiosa si en el futuro se
ingestan documentos de terceros, pero no mueve ninguna métrica actual.

---

## Criterio transversal de fusión

Toda rama hija debe:

1. Medir con `scripts/evaluar_banco.py` contra el mismo banco de 100 preguntas.
2. Comparar contra el baseline v1 (`tests/iteraciones/resultados_v1.json`).
3. Documentar el resultado **aunque sea negativo** — ver `experimento_prompt_v2.md`
   como referencia de experimento fallido bien registrado.
4. No fusionar si los fallos de generación totales suben respecto al baseline.
5. Actualizar este archivo y `Bitacora.md` antes de cerrar la rama.
