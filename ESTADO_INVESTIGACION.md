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

**Última actualización:** 2026-09-23, tras cerrar la iteración 1.1.

---

## Estado actual del sistema

Mejor configuración medida — **pipeline de dos pasos con `llama3.2` (3B) en
ambos roles + chunking de 1400 caracteres**, iteración 1.1:

```
RESPONDIBLES (50)     retrieval_hit@6 ........ 46/50 (92%, medido por archivo)
                      anclaje@6 .............. 25/36 (69%, medido por chunk)
                      abstuvo indebidamente .. 21/50
                      cobertura de datos ..... 57%

NO RESPONDIBLES (50)  ALUCINO ................   0/50 (0%)

JUEZ                  especificidad .......... 50/50 (100%)
                      precisión real ......... 46/50 (92%)

Duración .............................. 28,2 min   (juez 12,3 s/pregunta)
```

**Tensión abierta:** cada mejora de calidad se ha pagado en latencia. El juez
pasó de 6,4 s a 12,3 s al agrandar los fragmentos, porque el 98% de su costo es
leer contexto. Una consulta respondida cuesta ~28 s en una GTX 1650. Para un bot
de Telegram eso ya es mucho, y `k=8` lo encarecería otra vez.

**Dirección estratégica:** hacer rendir al modelo de 3B cambiando la
arquitectura, no sustituirlo por uno más grande. Un sistema que corre en
hardware modesto es el objetivo del proyecto, no una limitación a superar.

---

## Las siete líneas de investigación

| # | Línea | Estado | Evidencia |
|---|---|---|---|
| OP-3 | Modelo de generación | ❌ **Refutada** | 1.3 — escalar a 7-8B no baja la alucinación |
| OP-6 | Discriminación en dos pasos | ✅ **Confirmada** | 1.6 — alucinación 34% a 0% |
| OP-1 | Chunking | ✅ **Parcial** | 1.1 — el tamaño era la causa; 25 → 21 abstenciones |
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
| **Chunking estructural: un fragmento por sección markdown** | Implementado y medido en la 1.1: el anclaje cae de 22/36 a 18/36. Fragmentar más es PEOR. `_chunk_text` ya dividía por encabezados desde antes | `iteracion_1.1_chunking/resultado_1.1.md` |
| **Quitar el solape del chunking** | Neutro (22/36 → 22/36) a k=6 y negativo a k=10. El solape hace que los fragmentos empiecen a mitad de frase, pero su efecto neto es positivo: duplica los bordes y da una segunda oportunidad al dato | `iteracion_1.1_chunking/resultado_1.1.md` |
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
  costó una corrida entera poder atribuir el efecto. La 1.1 repitió el error con
  cinco variables juntas; la ablación (`scripts/ablacion_chunking.py`, ~10 s por
  variante) las separó y mostró que cuatro de las cinco estorbaban.
- **`anclaje@k` tiene techo 36, no 50.** 14 de las 50 citas del banco están
  parafraseadas y no existen literales en ningún `.md`, así que ninguna técnica
  de chunking puede darles positivo. Comparar contra 50 subestima el retrieval en
  28 puntos.
- **El tope del chunking está acoplado al truncado de `api.py`** (1400
  caracteres por fragmento). Subir uno sin el otro anula la mejora: el recorte
  vuelve a partir el dato justo antes de que el modelo lo lea.

---

## Detalle por línea

### OP-1 — Chunking ✅ **CONFIRMADA PARCIALMENTE**

Rama: `iteracion_1.1_chunking` · Plan y resultado en esa carpeta

**La causa era el tamaño del fragmento, no la estructura.** Con un tope de 800
caracteres la mayoría de las secciones del corpus no cabía entera y el dato
pedido quedaba partido entre dos fragmentos.

El cambio adoptado son dos constantes en `ingest.py`: `CHUNK_SIZE` 800 → 1400 y
`CHUNK_OVERLAP` 150 → 200.

```
                 antes    después
recall@6         44/50     46/50
anclaje@6        22/36     25/36
abstención ind.  25/50     21/50
alucinación       0/50      0/50
```

Primera iteración del proyecto que cumple su criterio de éxito. Recuperó **3 de
los 11** fallos a nivel de chunk, que es exactamente donde se esperaba que
actuara, sin mover las otras categorías de fallo.

Dos hipótesis previas quedaron **refutadas** en el camino (ver la tabla de
callejones sin salida): el chunking estructural por sección, y la eliminación
del solape.

**Lo que queda:** `k=8` sube el anclaje de 25/36 a 31/36 según la medición de
retrieval, con un cambio de una línea. Pero encarece al juez, que ya está en
12,3 s por pregunta. Medir end-to-end antes de adoptarlo.

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
